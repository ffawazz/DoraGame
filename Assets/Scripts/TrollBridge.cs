using System.Collections;
using UnityEngine;

/// <summary>
/// Grumpy Old Troll's bridge: planks drop out in a rhythm as Dora approaches.
/// Each plank is a child with a collider; fallen planks leave a gap Dora must jump.
/// Bridge floor beneath should be a kill-zone (tag "Hazard", trigger).
/// </summary>
public class TrollBridge : MonoBehaviour
{
    [SerializeField] Transform player;
    [SerializeField] Transform[] planks;              // ordered along +Z
    [SerializeField] float triggerDistance = 40f;
    [SerializeField] float warningShake = 0.35f;      // plank wobbles before dropping
    [SerializeField] float fallGravity = 25f;
    [SerializeField] int gapPeriod = 3;               // every Nth plank (+ pattern) drops
    [SerializeField] bool restorePlanksLater;         // Level 3: planks return, then collapse behind
    [SerializeField] AudioSource trollGrumble;

    bool triggered;

    void Update()
    {
        if (triggered || player == null) return;
        if (transform.position.z - player.position.z < triggerDistance)
        {
            triggered = true;
            if (trollGrumble) trollGrumble.Play();
            StartCoroutine(DropPattern());
        }
    }

    IEnumerator DropPattern()
    {
        for (int i = 0; i < planks.Length; i++)
        {
            if (i % gapPeriod != gapPeriod - 1) continue;
            // Drop two planks for a jumpable gap
            StartCoroutine(DropPlank(planks[i]));
            if (i + 1 < planks.Length) StartCoroutine(DropPlank(planks[i + 1]));
            yield return new WaitForSeconds(0.25f);
        }
    }

    IEnumerator DropPlank(Transform plank)
    {
        Vector3 home = plank.position;
        Quaternion rot = plank.rotation;

        // Wobble warning
        for (float t = 0; t < warningShake; t += Time.deltaTime)
        {
            plank.position = home + Random.insideUnitSphere * 0.05f;
            yield return null;
        }

        var col = plank.GetComponent<Collider>();
        if (col) col.enabled = false;

        float vy = 0f;
        for (float t = 0; t < 1.5f; t += Time.deltaTime)
        {
            vy -= fallGravity * Time.deltaTime;
            plank.position += Vector3.up * vy * Time.deltaTime;
            plank.Rotate(90f * Time.deltaTime, 0, 45f * Time.deltaTime);
            yield return null;
        }
        plank.gameObject.SetActive(false);

        if (restorePlanksLater)
        {
            yield return new WaitForSeconds(3f);
            plank.SetPositionAndRotation(home, rot);
            plank.gameObject.SetActive(true);
            if (col) col.enabled = true;
        }
    }
}
