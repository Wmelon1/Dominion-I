using UnityEngine;

namespace Dominion
{
    /// <summary>Shared IMGUI look for menus and HUD: dark translucent panels, steel-blue accents, scalable fonts.</summary>
    public static class Ui
    {
        static Texture2D panel, btn, btnHover, btnActive, white;
        public static GUIStyle Title, Subtitle, Button, Label, Center, Big, Small, Right, Shadow;
        public static readonly Color Accent = new Color(0.55f, 0.78f, 1f);
        public static readonly Color Gold = new Color(1f, 0.82f, 0.42f);
        static int lastH = -1;

        public static float S => Mathf.Max(0.5f, Screen.height / 1080f);

        static Texture2D Tex(Color c)
        {
            var t = new Texture2D(1, 1, TextureFormat.RGBA32, false) { hideFlags = HideFlags.HideAndDontSave };
            t.SetPixel(0, 0, c);
            t.Apply();
            return t;
        }

        /// <summary>Call at the top of every OnGUI.</summary>
        public static void Begin()
        {
            if (white == null)
            {
                white = Tex(Color.white);
                panel = Tex(new Color(0.04f, 0.06f, 0.09f, 0.78f));
                btn = Tex(new Color(0.09f, 0.13f, 0.19f, 0.88f));
                btnHover = Tex(new Color(0.18f, 0.32f, 0.48f, 0.95f));
                btnActive = Tex(new Color(0.3f, 0.5f, 0.72f, 1f));
                Title = new GUIStyle(GUI.skin.label) { alignment = TextAnchor.MiddleCenter, fontStyle = FontStyle.Bold, richText = true };
                Subtitle = new GUIStyle(GUI.skin.label) { alignment = TextAnchor.MiddleCenter, richText = true };
                Big = new GUIStyle(GUI.skin.label) { alignment = TextAnchor.MiddleCenter, fontStyle = FontStyle.Bold, richText = true };
                Label = new GUIStyle(GUI.skin.label) { richText = true, wordWrap = false };
                Small = new GUIStyle(GUI.skin.label) { richText = true, wordWrap = false };
                Right = new GUIStyle(GUI.skin.label) { richText = true, alignment = TextAnchor.UpperRight, wordWrap = false };
                Center = new GUIStyle(GUI.skin.label) { richText = true, alignment = TextAnchor.MiddleCenter, wordWrap = false };
                Shadow = new GUIStyle(Title);
                Button = new GUIStyle(GUI.skin.button) { alignment = TextAnchor.MiddleCenter, fontStyle = FontStyle.Bold, richText = true };
                Button.normal.background = btn;
                Button.hover.background = btnHover;
                Button.active.background = btnActive;
                Button.focused.background = btn;
                Button.normal.textColor = new Color(0.86f, 0.92f, 1f);
                Button.hover.textColor = Color.white;
                Button.active.textColor = Color.white;
                Button.border = new RectOffset(0, 0, 0, 0);
            }
            if (lastH != Screen.height)
            {
                lastH = Screen.height;
                float s = S;
                Title.fontSize = Mathf.RoundToInt(112 * s);
                Shadow.fontSize = Title.fontSize;
                Shadow.normal.textColor = new Color(0f, 0f, 0f, 0.55f);
                Subtitle.fontSize = Mathf.RoundToInt(24 * s);
                Big.fontSize = Mathf.RoundToInt(64 * s);
                Label.fontSize = Mathf.RoundToInt(20 * s);
                Small.fontSize = Mathf.RoundToInt(16 * s);
                Right.fontSize = Mathf.RoundToInt(17 * s);
                Center.fontSize = Mathf.RoundToInt(22 * s);
                Button.fontSize = Mathf.RoundToInt(28 * s);
            }
        }

        static Material glMat;
        static readonly System.Collections.Generic.List<(Rect r, Color c)> quads = new System.Collections.Generic.List<(Rect, Color)>();

        /// <summary>Queue a flat rectangle (drawn by FlushRects in one batch).</summary>
        public static void QueueRect(Rect r, Color c) => quads.Add((r, c));

        /// <summary>Draw every queued rectangle in one GL pass (call during the repaint event, in GUI pixel space).</summary>
        public static void FlushRects()
        {
            if (quads.Count == 0) return;
            if (Event.current == null || Event.current.type != EventType.Repaint) { quads.Clear(); return; }
            if (glMat == null)
            {
                glMat = new Material(Shader.Find("Hidden/Internal-Colored")) { hideFlags = HideFlags.HideAndDontSave };
                glMat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
                glMat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
                glMat.SetInt("_Cull", (int)UnityEngine.Rendering.CullMode.Off);
                glMat.SetInt("_ZWrite", 0);
                glMat.SetInt("_ZTest", (int)UnityEngine.Rendering.CompareFunction.Always);
            }
            glMat.SetPass(0);
            GL.PushMatrix();
            GL.LoadPixelMatrix(0f, Screen.width, Screen.height, 0f);
            GL.Begin(GL.QUADS);
            foreach (var (r, c) in quads)
            {
                GL.Color(c);
                GL.Vertex3(r.xMin, r.yMin, 0f);
                GL.Vertex3(r.xMax, r.yMin, 0f);
                GL.Vertex3(r.xMax, r.yMax, 0f);
                GL.Vertex3(r.xMin, r.yMax, 0f);
            }
            GL.End();
            GL.PopMatrix();
            quads.Clear();
        }

        public static void Rect(Rect r, Color c)
        {
            var old = GUI.color;
            GUI.color = c;
            GUI.DrawTexture(r, white);
            GUI.color = old;
        }

        public static void Panel(Rect r)
        {
            GUI.DrawTexture(r, panel);
            Rect(new Rect(r.x, r.y, r.width, Mathf.Max(2f, 3f * S)), new Color(Accent.r, Accent.g, Accent.b, 0.85f));
        }

        public static bool Btn(Rect r, string text) => GUI.Button(r, text, Button);

        public static string Hex(Color c) => ColorUtility.ToHtmlStringRGB(c);

        /// <summary>Text with a soft drop shadow (for titles over the 3D scene).</summary>
        public static void ShadowLabel(Rect r, string text, GUIStyle style)
        {
            var sh = new GUIStyle(style);
            sh.normal.textColor = new Color(0f, 0f, 0f, 0.6f);
            float o = Mathf.Max(1f, 3f * S);
            GUI.Label(new Rect(r.x + o, r.y + o, r.width, r.height), StripColor(text), sh);
            GUI.Label(r, text, style);
        }

        static string StripColor(string s) => System.Text.RegularExpressions.Regex.Replace(s, "<color=[^>]*>|</color>", "");
    }
}
