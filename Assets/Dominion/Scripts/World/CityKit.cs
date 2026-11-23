using System;
using System.Collections.Generic;
using UnityEngine;

namespace Dominion
{
    /// <summary>Everything the city generator places: filled in by the editor builder (Dominion > 7. Set Up City Kit).</summary>
    [CreateAssetMenu(menuName = "Dominion/City Kit")]
    public class CityKit : ScriptableObject
    {
        [Serializable]
        public class BuildingDef
        {
            public string name;
            /// <summary>Base type, e.g. Building_House (variants share it).</summary>
            public string type;
            public GameObject prefab;
            /// <summary>Footprint in the prefab's local x/z (front = +z), and roof height.</summary>
            public Vector2 min, max;
            public float height;
        }

        public List<BuildingDef> buildings = new List<BuildingDef>();
        public GameObject[] cars = new GameObject[0];
        public GameObject[] wrecks = new GameObject[0];
        public GameObject bus, busWreck;
        /// <summary>Oak, Maple, Street, Pine, PineTall.</summary>
        public GameObject[] trees = new GameObject[0];
        public GameObject streetLamp, trafficLight, bench, jersey, twall;

        public Material roadLocal, roadArterial, roadHighway, asphalt, sidewalk, curb, crosswalk, runway;
        public Material curtainWall, gravel, stone, metalDark, galvanized, corrugated, corrugatedRed, concrete;
        public Material[] curtain = new Material[0];
        public Material[] brick = new Material[0], plaster = new Material[0], facadeConcrete = new Material[0], storefront = new Material[0];
        /// <summary>Grass, Meadow, Dirt, Rock, Paving, LotGravel.</summary>
        public TerrainLayer[] layers = new TerrainLayer[0];
        public Material terrainMaterial;
    }
}
