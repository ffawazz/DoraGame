using UnityEngine;

/// <summary>
/// Behind-the-back chase camera: follows Dora's Z rigidly, lags on X for a sense of lane swoop,
/// widens FOV with speed, and adds a landing kick. (Use Cinemachine for production; this is a no-dependency stand-in.)
/// </summary>
[RequireComponent(typeof(Camera))]
public class RunnerCamera : MonoBehaviour
{
    [SerializeField] DoraRunnerController dora;
    [SerializeField] Vector3 offset = new Vector3(0f, 3.2f, -6.5f);
    [SerializeField] float lateralFollow = 6f;
    [SerializeField] float baseFov = 65f;
    [SerializeField] float maxFov = 90f;
    [SerializeField] float maxSpeedRef = 32f;
    [SerializeField] float lookAhead = 8f;

    Camera cam;
    float shake;

    void Awake() { cam = GetComponent<Camera>(); }

    void OnEnable()  { if (dora) dora.OnDeath += Kick; }
    void OnDisable() { if (dora) dora.OnDeath -= Kick; }

    public void Kick() { shake = 0.5f; }

    void LateUpdate()
    {
        if (dora == null) return;
        Vector3 p = dora.transform.position;

        float x = Mathf.Lerp(transform.position.x, p.x + offset.x, 1f - Mathf.Exp(-lateralFollow * Time.deltaTime));
        Vector3 pos = new Vector3(x, p.y * 0.4f + offset.y, p.z + offset.z);

        if (shake > 0f)
        {
            pos += Random.insideUnitSphere * shake * 0.3f;
            shake = Mathf.MoveTowards(shake, 0f, Time.deltaTime * 2f);
        }
        transform.position = pos;
        transform.LookAt(new Vector3(p.x * 0.6f, p.y * 0.5f + 1f, p.z + lookAhead));

        float t = Mathf.InverseLerp(0f, maxSpeedRef, dora.CurrentSpeed);
        cam.fieldOfView = Mathf.Lerp(cam.fieldOfView, Mathf.Lerp(baseFov, maxFov, t), Time.deltaTime * 4f);
    }
}
