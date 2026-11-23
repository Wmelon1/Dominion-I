using UnityEngine;
using UnityEngine.InputSystem;

namespace Dominion
{
    /// <summary>One frame of player intent. Filled from the keyboard/mouse (or by the auto-test).</summary>
    public struct ControlInput
    {
        public Vector2 move;          // WASD: x = A/D, y = W/S
        public bool sprint;           // Left Shift
        public bool crouch;           // Left Ctrl
        public bool fire;             // LMB held
        public bool aim;              // RMB held
        public bool jump;             // Space held
        public bool action1Down;      // F pressed (doors / ramp / canopy)
        public bool action2Down;      // G pressed (landing gear)
        public bool special;          // Q held (missile pods)
        public bool resetDown;        // R pressed (flip the vehicle back upright)
        public float yaw;             // Z/C: -1..1 (aircraft rudder)
        public Vector3 aimPoint;      // world point under the crosshair
        public float lookYaw;         // camera yaw (degrees)
        public float lookPitch;       // camera pitch (degrees)
    }

    /// <summary>Thin wrapper around the Input System devices (keyboard + mouse).</summary>
    public static class GameInput
    {
        static Keyboard K => Keyboard.current;
        static Mouse M => Mouse.current;

        public static bool Held(Key k) => K != null && K[k].isPressed;
        public static bool Down(Key k) => K != null && K[k].wasPressedThisFrame;
        static float Axis(Key neg, Key pos) => (Held(pos) ? 1f : 0f) - (Held(neg) ? 1f : 0f);

        public static bool CursorLocked => Cursor.lockState == CursorLockMode.Locked;
        public static Vector2 LookDelta => M != null && CursorLocked ? M.delta.ReadValue() : Vector2.zero;
        public static float Scroll => M != null ? M.scroll.ReadValue().y : 0f;
        public static bool LeftClickDown => M != null && M.leftButton.wasPressedThisFrame;

        public static ControlInput Read()
        {
            var c = new ControlInput
            {
                move = new Vector2(Axis(Key.A, Key.D), Axis(Key.S, Key.W)),
                sprint = Held(Key.LeftShift),
                crouch = Held(Key.LeftCtrl),
                fire = M != null && M.leftButton.isPressed && CursorLocked,
                aim = M != null && M.rightButton.isPressed && CursorLocked,
                jump = Held(Key.Space),
                action1Down = Down(Key.F),
                action2Down = Down(Key.G),
                special = Held(Key.Q),
                resetDown = Down(Key.R),
                yaw = Axis(Key.Z, Key.C),
            };
            if (c.move.sqrMagnitude > 1f) c.move.Normalize();
            return c;
        }
    }
}
