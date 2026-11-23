using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>
    /// Name -> bone lookup with rest pose, plus geometry-based helpers so rotations never depend on how the
    /// FBX importer converted bone axes: every rotation axis is derived from the vehicle's own frame at rest.
    /// </summary>
    public class RigBones
    {
        readonly Dictionary<string, Transform> map = new Dictionary<string, Transform>();
        readonly Dictionary<Transform, Quaternion> restRot = new Dictionary<Transform, Quaternion>();
        readonly Dictionary<Transform, Vector3> restPos = new Dictionary<Transform, Vector3>();
        readonly Dictionary<Transform, Vector3> restScale = new Dictionary<Transform, Vector3>();
        public readonly Transform root;

        public RigBones(Transform root)
        {
            this.root = root;
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
            {
                if (!map.ContainsKey(t.name)) map[t.name] = t;
                restRot[t] = t.localRotation;
                restPos[t] = t.localPosition;
                restScale[t] = t.localScale;
            }
        }

        public Transform this[string n] => n != null && map.TryGetValue(n, out var t) ? t : null;
        public bool Has(string n) => n != null && map.ContainsKey(n);
        public IEnumerable<Transform> All => map.Values;
        public Quaternion RestRot(Transform t) => restRot.TryGetValue(t, out var q) ? q : t.localRotation;
        public Vector3 RestPos(Transform t) => restPos.TryGetValue(t, out var p) ? p : t.localPosition;
        public Vector3 RestScale(Transform t) => restScale.TryGetValue(t, out var s) ? s : t.localScale;

        /// <summary>A world direction expressed in the bone's own local frame (call in the rest pose).</summary>
        public static Vector3 LocalAxis(Transform bone, Vector3 worldDir) => (Quaternion.Inverse(bone.rotation) * worldDir).normalized;

        /// <summary>Set rotation = rest * AngleAxis(deg, localAxis).</summary>
        public void Rotate(Transform bone, Vector3 localAxis, float deg)
        {
            if (bone) bone.localRotation = RestRot(bone) * Quaternion.AngleAxis(deg, localAxis);
        }

        public void Scale(Transform bone, float s)
        {
            if (bone) bone.localScale = RestScale(bone) * s;
        }

        /// <summary>Slide a bone along its own Y axis (Blender bone direction) by d metres.</summary>
        public void SlideY(Transform bone, float d)
        {
            if (bone) bone.localPosition = RestPos(bone) + RestRot(bone) * Vector3.up * d;
        }

        /// <summary>
        /// Sign (+1/-1) so that rotating bone by +deg about localAxis moves a probe on the bone AWAY from 'center'
        /// (used for doors, ramps, canopies). Probe = the bone-attached point that moves most.
        /// </summary>
        public static float OpenSign(Transform bone, Vector3 localAxis, float deg, Vector3 center)
        {
            Vector3[] probes = { Vector3.up, Vector3.forward, Vector3.right, Vector3.down, Vector3.back, Vector3.left };
            Quaternion r0 = bone.rotation;
            Quaternion r1 = r0 * Quaternion.AngleAxis(deg, localAxis);
            float best = 0f, sign = 1f;
            foreach (var pr in probes)
            {
                Vector3 a = bone.position + r0 * pr;
                Vector3 b = bone.position + r1 * pr;
                float moved = (b - a).magnitude;
                if (moved > best)
                {
                    best = moved;
                    float grow = (b - center).magnitude - (a - center).magnitude;
                    float down = a.y - b.y;
                    sign = (grow + 0.25f * down) >= 0f ? 1f : -1f;
                }
            }
            return sign;
        }
    }
}
