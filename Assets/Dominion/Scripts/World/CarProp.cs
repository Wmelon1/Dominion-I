using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// A parked car, bus or wreck. Tanks, armoured vehicles and mechs drive straight over it: the car is flattened and
    /// stops blocking (its collider goes), so heavy units path through parked cars instead of around them.
    /// </summary>
    public class CarProp : MonoBehaviour
    {
        public bool Crushed { get; private set; }
        public static int CrushedCount;

        public void Crush(Vector3 from)
        {
            if (Crushed) return;
            Crushed = true;
            CrushedCount++;
            foreach (var c in GetComponentsInChildren<Collider>()) c.enabled = false;
            if (GetComponentInChildren<Renderer>() != null)
            {
                // flattened where the tracks went over it, slightly skewed
                var t = transform;
                Vector3 s = t.localScale;
                t.localScale = new Vector3(s.x * 1.07f, s.y * 0.33f, s.z * 1.04f);
                t.rotation *= Quaternion.Euler(Random.Range(-3f, 3f), 0f, Random.Range(-6f, 6f));
            }
            Vfx.DustPuff(transform.position + Vector3.up * 0.4f, 1.2f);
            Vfx.SmallImpact(transform.position + Vector3.up * 0.6f, (transform.position - from).normalized + Vector3.up, true, 1.4f);
        }
    }
}
