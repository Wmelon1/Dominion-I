using UnityEngine;

namespace Dominion
{
    /// <summary>Third-person camera: over-the-shoulder for soldiers, orbit for ground vehicles, chase for aircraft.</summary>
    public class CameraRig : MonoBehaviour
    {
        public static CameraRig Main { get; private set; }
        public float sensitivity = 0.11f;
        public float yaw, pitch = 12f;
        [System.NonSerialized] public bool inputEnabled = true;

        System.Func<Vector3> pivot;
        Vector3 shoulder;
        float distance = 4f, wantDistance = 4f, minDist = 2f, maxDist = 60f;
        Transform chase;
        Transform ignoreRoot;
        float chaseYaw, chasePitch, idleT;
        Quaternion chaseRot = Quaternion.identity;

        public Transform IgnoreRoot => ignoreRoot;
        float shake;

        void Awake() => Main = this;

        /// <summary>Kick the camera (0..1), decays over ~0.5 s.</summary>
        public void Shake(float amount) => shake = Mathf.Max(shake, Mathf.Clamp01(amount));

        public void FollowSoldier(SoldierController s)
        {
            pivot = () => s.CameraPivot;
            shoulder = new Vector3(0.55f, 0.05f, 0f);
            wantDistance = distance = 3.4f;
            minDist = 1.6f;
            maxDist = 8f;
            chase = null;
            ignoreRoot = s.transform;
        }

        public void FollowVehicle(Vehicle v, bool chaseMode)
        {
            pivot = () => v.CameraPivot;
            shoulder = Vector3.zero;
            wantDistance = v.CameraDistance;
            minDist = wantDistance * 0.4f;
            maxDist = wantDistance * 2.5f;
            chase = chaseMode ? v.transform : null;
            chaseRot = v.transform.rotation;
            chaseYaw = chasePitch = 0f;
            ignoreRoot = v.transform;
            if (!chaseMode)
            {
                yaw = v.transform.eulerAngles.y;
                pitch = 14f;
            }
        }

        static readonly RaycastHit[] camHits = new RaycastHit[16];

        void LateUpdate()
        {
            if (pivot == null) return;
            float dt = Time.deltaTime;
            Vector2 look = inputEnabled ? GameInput.LookDelta * sensitivity : Vector2.zero;
            if (inputEnabled) wantDistance = Mathf.Clamp(wantDistance * (1f - GameInput.Scroll * 0.001f), minDist, maxDist);
            distance = Mathf.Lerp(distance, wantDistance, 1f - Mathf.Exp(-8f * dt));
            Vector3 p = pivot();
            Quaternion rot;
            if (chase)
            {
                chaseYaw += look.x;
                chasePitch = Mathf.Clamp(chasePitch - look.y, -60f, 60f);
                idleT = look.sqrMagnitude > 0.01f ? 0f : idleT + dt;
                if (idleT > 1.2f)
                {
                    chaseYaw = Mathf.Lerp(chaseYaw, 0f, 1f - Mathf.Exp(-3f * dt));
                    chasePitch = Mathf.Lerp(chasePitch, 0f, 1f - Mathf.Exp(-3f * dt));
                }
                Quaternion follow = Quaternion.LookRotation(chase.forward, Vector3.Lerp(Vector3.up, chase.up, 0.35f));
                chaseRot = Quaternion.Slerp(chaseRot, follow, 1f - Mathf.Exp(-5f * dt));
                rot = chaseRot * Quaternion.Euler(10f + chasePitch, chaseYaw, 0f);
                yaw = rot.eulerAngles.y;
                pitch = Mathf.DeltaAngle(0f, rot.eulerAngles.x);
            }
            else
            {
                yaw += look.x;
                pitch = Mathf.Clamp(pitch - look.y, -40f, 75f);
                rot = Quaternion.Euler(pitch, yaw, 0f);
            }
            Vector3 cam = p + rot * (shoulder + Vector3.back * distance);
            // keep the camera out of walls and buildings (units, including the one we follow, are ignored)
            Vector3 dir = cam - p;
            float len = dir.magnitude;
            if (len > 0.2f)
            {
                int n = Physics.SphereCastNonAlloc(p, 0.25f, dir / len, camHits, len, ~0, QueryTriggerInteraction.Ignore);
                float best = len;
                for (int i = 0; i < n; i++)
                {
                    var c = camHits[i].collider;
                    if (camHits[i].distance <= 0f || (ignoreRoot && c.transform.IsChildOf(ignoreRoot)) || Health.Of(c) != null) continue;
                    if (camHits[i].distance < best) best = camHits[i].distance;
                }
                if (best < len) cam = p + dir / len * Mathf.Max(0.35f, best - 0.12f);
            }
            float floor = WorldGround.Height(cam.x, cam.z) + 0.35f;
            if (cam.y < floor) cam.y = floor;
            if (shake > 0.001f)
            {
                cam += Random.insideUnitSphere * (shake * 0.6f);
                rot *= Quaternion.Euler(Random.Range(-1f, 1f) * shake * 2f, Random.Range(-1f, 1f) * shake * 2f, 0f);
                shake = Mathf.MoveTowards(shake, 0f, dt * 2f);
            }
            transform.SetPositionAndRotation(cam, rot);
        }

        /// <summary>World point under the screen centre, ignoring the followed object.</summary>
        public Vector3 AimPoint()
        {
            var ray = new Ray(transform.position, transform.forward);
            var hits = Physics.RaycastAll(ray, 3000f, ~0, QueryTriggerInteraction.Ignore);
            float best = 3000f;
            Vector3 point = ray.GetPoint(1500f);
            foreach (var h in hits)
            {
                if (ignoreRoot && h.collider.transform.IsChildOf(ignoreRoot)) continue;
                if (h.distance < best && h.distance > 1f)
                {
                    best = h.distance;
                    point = h.point;
                }
            }
            return point;
        }
    }
}
