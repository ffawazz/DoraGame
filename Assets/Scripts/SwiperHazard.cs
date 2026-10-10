using System.Collections;
using UnityEngine;

/// <summary>
/// Swiper the Fox: when Dora gets close he leaps out beside the road, telegraphs a lane,
/// and hurls junk into it. Place on a chunk; assign a junk prefab with a "Hazard"-tagged trigger collider.
/// </summary>
public class SwiperHazard : MonoBehaviour
{
    [SerializeField] Transform player;
    [SerializeField] GameObject junkPrefab;
    [SerializeField] Transform hidePoint;             // off-road hiding spot
    [SerializeField] Transform popOutPoint;           // beside the road
    [SerializeField] GameObject laneWarning;          // optional flashing lane marker
    [SerializeField] float triggerDistance = 45f;
    [SerializeField] float telegraphTime = 0.6f;      // fair warning at speed
    [SerializeField] float junkSpeed = 22f;
    [SerializeField] float laneWidth = 2.5f;
    [SerializeField] int throws = 3;
    [SerializeField] float throwInterval = 0.8f;
    [SerializeField] AudioSource ohMan;               // "Oh, man!"

    bool triggered;

    void Update()
    {
        if (triggered || player == null) return;
        if (transform.position.z - player.position.z < triggerDistance)
        {
            triggered = true;
            StartCoroutine(Ambush());
        }
    }

    IEnumerator Ambush()
    {
        // Leap out
        yield return MoveTo(popOutPoint.position, 0.25f);
        if (ohMan) ohMan.Play();

        for (int i = 0; i < throws; i++)
        {
            int lane = Random.Range(0, 3);
            float laneX = (lane - 1) * laneWidth;

            // Telegraph the target lane
            if (laneWarning)
            {
                laneWarning.transform.position = new Vector3(laneX, laneWarning.transform.position.y, player.position.z + 25f);
                laneWarning.SetActive(true);
            }
            yield return new WaitForSeconds(telegraphTime);
            if (laneWarning) laneWarning.SetActive(false);

            // Throw junk down the lane toward Dora
            var junk = Instantiate(junkPrefab, popOutPoint.position, Random.rotation);
            StartCoroutine(FlyJunk(junk.transform, new Vector3(laneX, 0.5f, popOutPoint.position.z)));
            yield return new WaitForSeconds(throwInterval);
        }

        yield return MoveTo(hidePoint.position, 0.3f);
    }

    IEnumerator FlyJunk(Transform junk, Vector3 landing)
    {
        // Arc to the lane, then roll backward toward Dora
        Vector3 start = junk.position;
        for (float t = 0; t < 1f; t += Time.deltaTime * 3f)
        {
            if (!junk) yield break;
            Vector3 p = Vector3.Lerp(start, landing, t);
            p.y += Mathf.Sin(t * Mathf.PI) * 3f;
            junk.position = p;
            junk.Rotate(360f * Time.deltaTime, 0, 180f * Time.deltaTime);
            yield return null;
        }
        while (junk && junk.position.z > player.position.z - 10f)
        {
            junk.position += Vector3.back * junkSpeed * Time.deltaTime;
            junk.Rotate(540f * Time.deltaTime, 0, 0);
            yield return null;
        }
        if (junk) Destroy(junk.gameObject);
    }

    IEnumerator MoveTo(Vector3 target, float duration)
    {
        Vector3 start = transform.position;
        for (float t = 0; t < 1f; t += Time.deltaTime / duration)
        {
            transform.position = Vector3.Lerp(start, target, Mathf.SmoothStep(0, 1, t));
            yield return null;
        }
        transform.position = target;
    }
}
