using UnityEngine;

/// <summary>
/// Dora's endless-forward runner controller (Pepsi Man style).
/// - Auto-runs along +Z with escalating speed
/// - Three lanes, snappy lerped lane changes
/// - Jump (gravity-scaled for a punchy arc) and slide (shrinks the CharacterController)
/// - Input buffering + coyote time so it feels fair at high speed
/// Requires a CharacterController on the same GameObject.
/// </summary>
[RequireComponent(typeof(CharacterController))]
public class DoraRunnerController : MonoBehaviour
{
    [Header("Forward Momentum")]
    [SerializeField] float startSpeed = 12f;
    [SerializeField] float maxSpeed = 32f;
    [SerializeField] float acceleration = 0.35f;      // m/s gained per second

    [Header("Lanes")]
    [SerializeField] float laneWidth = 2.5f;
    [SerializeField] float laneChangeSpeed = 18f;     // higher = snappier

    [Header("Jump")]
    [SerializeField] float jumpHeight = 2.2f;
    [SerializeField] float gravity = -45f;            // heavy gravity = arcade feel
    [SerializeField] float coyoteTime = 0.1f;
    [SerializeField] float inputBufferTime = 0.15f;

    [Header("Slide")]
    [SerializeField] float slideDuration = 0.7f;
    [SerializeField] float slideHeight = 0.7f;
    [SerializeField] float fastFallSpeed = -40f;      // slide in mid-air to slam down

    [Header("Swipe Input (touch/mouse optional)")]
    [SerializeField] float swipeThreshold = 60f;

    public enum RunState { Running, Sliding, Dead, Finished }
    public RunState State { get; private set; } = RunState.Running;

    public float CurrentSpeed { get; private set; }
    public int CurrentLane { get; private set; } = 1; // 0 = left, 1 = middle, 2 = right

    CharacterController cc;
    float originalHeight;
    Vector3 originalCenter;
    float verticalVelocity;
    float lastGroundedTime = -10f;
    float jumpBufferedAt = -10f;
    float slideEndsAt;
    Vector2 swipeStart;
    float startX;

    // Hook these up to animation / audio / UI ("Dora: ¡Vámonos!")
    public event System.Action OnJump, OnSlide, OnLaneChange, OnDeath, OnFinish;

    void Awake()
    {
        cc = GetComponent<CharacterController>();
        originalHeight = cc.height;
        originalCenter = cc.center;
        startX = transform.position.x;
        CurrentSpeed = startSpeed;
    }

    void Update()
    {
        if (State == RunState.Dead || State == RunState.Finished) return;

        ReadInput();
        UpdateSpeed();
        UpdateSlide();
        Move();
    }

    // ---------------- Input ----------------
    void ReadInput()
    {
        if (Input.GetKeyDown(KeyCode.A) || Input.GetKeyDown(KeyCode.LeftArrow))  ChangeLane(-1);
        if (Input.GetKeyDown(KeyCode.D) || Input.GetKeyDown(KeyCode.RightArrow)) ChangeLane(+1);
        if (Input.GetKeyDown(KeyCode.W) || Input.GetKeyDown(KeyCode.UpArrow) || Input.GetKeyDown(KeyCode.Space))
            jumpBufferedAt = Time.time;
        if (Input.GetKeyDown(KeyCode.S) || Input.GetKeyDown(KeyCode.DownArrow))  StartSlide();

        // Simple mouse/touch swipe support
        if (Input.GetMouseButtonDown(0)) swipeStart = Input.mousePosition;
        if (Input.GetMouseButtonUp(0))
        {
            Vector2 d = (Vector2)Input.mousePosition - swipeStart;
            if (d.magnitude < swipeThreshold) return;
            if (Mathf.Abs(d.x) > Mathf.Abs(d.y)) ChangeLane(d.x > 0 ? +1 : -1);
            else if (d.y > 0) jumpBufferedAt = Time.time;
            else StartSlide();
        }
    }

    // ---------------- Speed ----------------
    void UpdateSpeed()
    {
        CurrentSpeed = Mathf.Min(CurrentSpeed + acceleration * Time.deltaTime, maxSpeed);
    }

    // ---------------- Lanes ----------------
    void ChangeLane(int dir)
    {
        int target = Mathf.Clamp(CurrentLane + dir, 0, 2);
        if (target == CurrentLane) return;
        CurrentLane = target;
        OnLaneChange?.Invoke();
    }

    float TargetX => startX + (CurrentLane - 1) * laneWidth;

    // ---------------- Slide ----------------
    void StartSlide()
    {
        if (State == RunState.Sliding) return;

        if (!cc.isGrounded)
        {
            verticalVelocity = fastFallSpeed; // slam down to the ground, then slide
        }

        State = RunState.Sliding;
        slideEndsAt = Time.time + slideDuration;

        // Shrink the capsule, keeping the feet planted
        cc.height = slideHeight;
        cc.center = new Vector3(originalCenter.x, slideHeight * 0.5f, originalCenter.z);
        OnSlide?.Invoke();
    }

    void UpdateSlide()
    {
        if (State == RunState.Sliding && Time.time >= slideEndsAt && !HeadBlocked()) EndSlide();
    }

    // Stay low while a barrier is still overhead
    bool HeadBlocked()
    {
        Vector3 origin = transform.position + Vector3.up * slideHeight;
        return Physics.Raycast(origin, Vector3.up, originalHeight - slideHeight, ~0, QueryTriggerInteraction.Ignore);
    }

    void EndSlide()
    {
        cc.height = originalHeight;
        cc.center = originalCenter;
        State = RunState.Running;
    }

    // ---------------- Movement ----------------
    void Move()
    {
        bool grounded = cc.isGrounded;
        if (grounded)
        {
            lastGroundedTime = Time.time;
            if (verticalVelocity < 0f) verticalVelocity = -2f; // stick to ground
        }

        // Jump with coyote time + buffered input
        bool canJump = Time.time - lastGroundedTime <= coyoteTime;
        bool wantsJump = Time.time - jumpBufferedAt <= inputBufferTime;
        if (canJump && wantsJump)
        {
            if (State == RunState.Sliding) EndSlide();
            verticalVelocity = Mathf.Sqrt(jumpHeight * -2f * gravity);
            jumpBufferedAt = -10f;
            lastGroundedTime = -10f;
            OnJump?.Invoke();
        }

        verticalVelocity += gravity * Time.deltaTime;

        // Smooth lateral snap to the target lane (frame-rate independent)
        float newX = Mathf.Lerp(transform.position.x, TargetX, 1f - Mathf.Exp(-laneChangeSpeed * Time.deltaTime));
        float dx = newX - transform.position.x;

        Vector3 motion = new Vector3(dx, verticalVelocity * Time.deltaTime, CurrentSpeed * Time.deltaTime);
        cc.Move(motion);
    }

    // ---------------- Collisions ----------------
    // Tag obstacles "Hazard" (trigger colliders), the finish line "Finish" (the Banana Swing).
    void OnTriggerEnter(Collider other)
    {
        if (State == RunState.Dead || State == RunState.Finished) return;

        if (other.CompareTag("Hazard")) Die();
        else if (other.CompareTag("Finish")) Finish(other.transform);
        else if (other.CompareTag("Collectible")) Destroy(other.gameObject); // hook up score here
    }

    void Die()
    {
        State = RunState.Dead;
        OnDeath?.Invoke(); // play comedic ragdoll / "Oh no!" and respawn at checkpoint
    }

    void Finish(Transform swing)
    {
        State = RunState.Finished;
        enabled = false;
        OnFinish?.Invoke(); // trigger the Banana Swing victory cutscene
        // e.g. attach to swing: transform.SetParent(swing); animator.SetTrigger("SwingWin");
    }
}
