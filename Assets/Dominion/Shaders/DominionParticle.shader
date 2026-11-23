// Dominion I particle shader for HDRP (Shuriken particle systems).
// Per-particle colour / alpha from vertex colour, alpha or additive blending, soft particles against the depth
// buffer. Output is display-referred (not scaled by HDRP exposure), so smoke stays readable in bright daylight
// and fire / sparks above 1.0 drive bloom.
Shader "Dominion/Particle"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
        _Tint ("Tint", Color) = (1, 1, 1, 1)
        _Brightness ("Brightness", Float) = 1
        _SoftDistance ("Soft particle distance (m)", Float) = 1.5
        [Enum(UnityEngine.Rendering.BlendMode)] _SrcBlend ("Src Blend", Float) = 5
        [Enum(UnityEngine.Rendering.BlendMode)] _DstBlend ("Dst Blend", Float) = 10
    }
    SubShader
    {
        Tags { "RenderPipeline" = "HDRenderPipeline" "RenderType" = "Transparent" "Queue" = "Transparent" "IgnoreProjector" = "True" }
        Pass
        {
            Name "ForwardOnly"
            Tags { "LightMode" = "ForwardOnly" }
            Blend [_SrcBlend] [_DstBlend]
            ZWrite Off
            ZTest LEqual
            Cull Off

            HLSLPROGRAM
            #pragma target 4.5
            #pragma only_renderers d3d11 playstation xboxone xboxseries vulkan metal switch switch2
            #pragma vertex Vert
            #pragma fragment Frag

            #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/Common.hlsl"
            #include "Packages/com.unity.render-pipelines.high-definition/Runtime/ShaderLibrary/ShaderVariables.hlsl"

            TEXTURE2D(_MainTex);
            SAMPLER(sampler_MainTex);

            CBUFFER_START(UnityPerMaterial)
                float4 _MainTex_ST;
                float4 _Tint;
                float _Brightness;
                float _SoftDistance;
                float _SrcBlend;
                float _DstBlend;
            CBUFFER_END

            struct Attributes
            {
                float3 positionOS : POSITION;
                float4 color : COLOR;
                float2 uv : TEXCOORD0;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float4 color : COLOR;
                float2 uv : TEXCOORD0;
            };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                float3 positionWS = TransformObjectToWorld(v.positionOS);    // camera-relative in HDRP
                o.positionCS = TransformWorldToHClip(positionWS);
                o.color = v.color;
                o.uv = v.uv * _MainTex_ST.xy + _MainTex_ST.zw;
                return o;
            }

            float4 Frag(Varyings i) : SV_Target
            {
                float4 tex = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv);
                float4 c = tex * i.color * _Tint;
                // soft particles: fade where the sprite cuts into the ground / vehicles
                float sceneDepth = LinearEyeDepth(LoadCameraDepth(uint2(i.positionCS.xy)), _ZBufferParams);
                float fade = saturate((sceneDepth - i.positionCS.w) / max(_SoftDistance, 1e-3));
                c.a *= fade;
                c.rgb *= _Brightness;
                // additive materials (Dst = One) use premultiplied colour: scale by alpha so faded particles vanish
                if (_DstBlend == 1) c.rgb *= c.a;
                return c;
            }
            ENDHLSL
        }
    }
}
