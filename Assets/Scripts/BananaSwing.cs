using System.Collections;
using UnityEngine;

/// <summary>
/// The goal of every level. Place at the end of the finish chunk with a trigger collider tagged "Finish".
/// When Dora hits the trigger (DoraRunnerController.OnFinish), she is pulled along a leaping arc
/// onto the swing seat, then the swing rocks and victory FX play.
/// </summary>
[RequireComponent(typeof(Collider))]
public class BananaSwing : MonoBehaviour
{
    [SerializeField] Transform seat;                  // where Dora lands
    [SerializeField] Transform swingPivot;            // rotates to rock the swing
    [SerializeField] float leapDuration = 0.9f;
    [SerializeField] float leapHeight = 3f;
    [SerializeField] float swingAngle = 35f;
    [SerializeField] float swingSpeed = 2.5f;
    [SerializeField] ParticleSystem confetti;
    [SerializeField] AudioSource victoryJingle;       // "We did it!"
    [SerializeField] string victoryTrigger = "SwingWin";

    void Reset() { GetComponent<Collider>().isTrigger = true; gameObject.tag = "Finish"; }

    void OnTriggerEnter(Collider other)
    {
        var dora = other.GetComponent<DoraRunnerController>();
        if (dora == null) return;
        StartCoroutine(Celebrate(dora));
    }

    IEnumerator Celebrate(DoraRunnerController dora)
    {
        // DoraRunnerController disables itself on Finish, so we drive her transform here.
        var cc = dora.GetComponent<CharacterController>();
        cc.enabled = false;

        // Slow-mo hero leap
        Time.timeScale = 0.5f;
        Vector3 start = dora.transform.position;
        Vector3 end = seat.position;
        for (float t = 0; t < 1f; t += Time.unscaledDeltaTime / leapDuration)
        {
            Vector3 p = Vector3.Lerp(start, end, t);
            p.y += Mathf.Sin(t * Mathf.PI) * leapHeight;
            dora.transform.position = p;
            dora.transform.Rotate(0, 0, 720f * Time.unscaledDeltaTime / leapDuration); // victory flip
            yield return null;
        }
        Time.timeScale = 1f;

        dora.transform.SetParent(seat);
        dora.transform.localPosition = Vector3.zero;
        dora.transform.localRotation = Quaternion.identity;

        var anim = dora.GetComponentInChildren<Animator>();
        if (anim) anim.SetTrigger(victoryTrigger);
        if (confetti) confetti.Play();
        if (victoryJingle) victoryJingle.Play();

        // Rock the swing forever (until the results screen loads)
        while (true)
        {
            float a = Mathf.Sin(Time.time * swingSpeed) * swingAngle;
            if (swingPivot) swingPivot.localRotation = Quaternion.Euler(a, 0, 0);
            yield return null;
        }
    }
}
