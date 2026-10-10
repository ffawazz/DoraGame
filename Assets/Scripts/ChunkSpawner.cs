using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Endless-then-finite level builder. Spawns hand-authored chunk prefabs ahead of Dora,
/// recycles chunks behind her, and ends the stage with a Banana Swing finish chunk.
/// Each chunk prefab: pivot at its start edge, length == chunkLength along +Z.
/// </summary>
public class ChunkSpawner : MonoBehaviour
{
    [SerializeField] Transform player;
    [SerializeField] GameObject startChunk;          // safe warm-up (no hazards)
    [SerializeField] GameObject[] chunkPrefabs;      // easy -> hard variety
    [SerializeField] GameObject finishChunk;         // contains the Banana Swing ("Finish" tag)
    [SerializeField] float chunkLength = 30f;
    [SerializeField] int chunksAhead = 6;
    [SerializeField] int totalChunks = 24;           // stage length before the finish
    [SerializeField] int seed = 0;                   // 0 = random

    readonly Queue<GameObject> active = new Queue<GameObject>();
    readonly Dictionary<GameObject, Stack<GameObject>> pool = new Dictionary<GameObject, Stack<GameObject>>();
    readonly Dictionary<GameObject, GameObject> sourceOf = new Dictionary<GameObject, GameObject>();
    int spawned;
    float nextZ;
    System.Random rng;

    void Start()
    {
        rng = seed == 0 ? new System.Random() : new System.Random(seed);
        nextZ = transform.position.z;
        Spawn(startChunk);
        for (int i = 0; i < chunksAhead; i++) SpawnNext();
    }

    void Update()
    {
        // Keep the road filled ahead of the player
        while (spawned <= totalChunks && nextZ < player.position.z + chunksAhead * chunkLength)
            SpawnNext();

        // Recycle chunks that are well behind
        while (active.Count > 0 && active.Peek().transform.position.z + chunkLength < player.position.z - chunkLength)
            Recycle(active.Dequeue());
    }

    void SpawnNext()
    {
        if (spawned > totalChunks) return;
        if (spawned == totalChunks) { Spawn(finishChunk); spawned++; return; }

        // Difficulty curve: later chunks are drawn from the harder end of the array
        float t = (float)spawned / totalChunks;
        int max = Mathf.Clamp(Mathf.CeilToInt(t * chunkPrefabs.Length) + 1, 1, chunkPrefabs.Length);
        Spawn(chunkPrefabs[rng.Next(0, max)]);
        spawned++;
    }

    void Spawn(GameObject prefab)
    {
        GameObject go;
        if (pool.TryGetValue(prefab, out var stack) && stack.Count > 0)
        {
            go = stack.Pop();
            go.SetActive(true);
        }
        else
        {
            go = Instantiate(prefab, transform);
            sourceOf[go] = prefab;
        }
        go.transform.position = new Vector3(transform.position.x, transform.position.y, nextZ);
        nextZ += chunkLength;
        active.Enqueue(go);
    }

    void Recycle(GameObject go)
    {
        go.SetActive(false);
        var prefab = sourceOf[go];
        if (!pool.TryGetValue(prefab, out var stack)) pool[prefab] = stack = new Stack<GameObject>();
        stack.Push(go);
    }
}
