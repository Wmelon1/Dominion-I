using System;

namespace Dominion
{
    /// <summary>
    /// War settings carried from the title screen into the War scene: the map seed (0 = roll a new one), the army size
    /// per side, and the map's name. Every seed always builds the same city, and its name comes from the database below
    /// (a hash of the seed picks it). Command line: -seed N, -army 50|100|200.
    /// </summary>
    public static class MapInfo
    {
        public static int Seed;
        public static int ArmySize = 200;
        public static int LastSeed;
        public static readonly int[] ArmySizes = { 50, 100, 200 };

        public static int RandomSeed() => new Random(Guid.NewGuid().GetHashCode()).Next(1, 1000000);

        public static string NameOf(int seed)
        {
            uint h = (uint)seed;
            h ^= h >> 16; h *= 0x7feb352dU; h ^= h >> 15; h *= 0x846ca68bU; h ^= h >> 16;
            return Names[h % (uint)Names.Length];
        }

        static bool argsApplied;

        /// <summary>Applies -seed / -army once per launch, so New Map and the title screen's choices still work afterwards.</summary>
        public static void FromCommandLine()
        {
            if (argsApplied) return;
            argsApplied = true;
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i] == "-seed" && int.TryParse(args[i + 1], out int s)) Seed = s;
                if (args[i] == "-army" && int.TryParse(args[i + 1], out int a)) ArmySize = a <= 50 ? 50 : a <= 100 ? 100 : 200;
            }
        }

        /// <summary>The map-name database (fictional cities).</summary>
        public static readonly string[] Names =
        {
            "Ardenport", "Valcrest", "Halvorsk", "New Tyrell", "Port Kessan", "Braxton Falls", "Corvane", "Eastmere",
            "Dunmoor", "Kaleth", "Mirova", "Novagrad", "Saltreach", "Westhollow", "Thornbury", "Larkspur", "Calder Bay",
            "Redmarsh", "Oskaro", "Velmont", "Greywater", "Haldane", "Ironvale", "Kestrel Point", "Marrowick", "Ostrell",
            "Pellmar", "Quintana", "Ravensholm", "Sabrecliff", "Tarnow Heights", "Umberfield", "Varnholt", "Wexley",
            "Yarrowgate", "Zelenko", "Ashford Crossing", "Belmora", "Carrow", "Drevansk", "Elmshade", "Fallowmere",
            "Gorsk", "Harrowgate", "Istria Nova", "Jessop", "Kirovale", "Lindqvist", "Merrow Bay", "Northcairn",
            "Orlenko", "Port Halden", "Ravel", "Stonebridge", "Tamsin", "Ulverholm", "Valdora", "Westerlund", "Yelin",
            "Zarovo", "Aldermoor", "Brightwater", "Castellan", "Dorrington", "Emberly", "Fenwick", "Glasskirk",
            "Highmarsh", "Ivory Point", "Juniper Ridge", "Karsk", "Lowenthal", "Merrivale", "Nordhaven", "Oakhurst",
            "Pryzna", "Quarry Hill", "Rosendal", "Silverton", "Tolvaj", "Upperton", "Vashti", "Wrenfield", "Xandria",
            "Yarlow", "Zennor", "Arkhaven", "Blackrock", "Coldspring", "Deverell", "Eskmoor", "Farrowdale", "Gallant",
            "Hollins", "Irongate", "Jaskow", "Kilmara", "Lorvan", "Montclair Vale", "Newcastle Marsh", "Orsova",
            "Penrith Cross", "Queensbridge", "Riverton", "Sandhurst", "Tyrnovo", "Utgard", "Vintersby", "Willowmere",
            "Ystrad", "Zagora", "Amberley", "Bastogne Hill", "Corrin", "Danvers", "Eldridge", "Falkner Crossing",
            "Grimsby Vale", "Hartwell", "Islington Moor", "Jorvik Fields", "Kensal", "Lambeth Rise", "Malvorn",
            "Netherby", "Oxwich", "Portland Reach", "Ramsgate Hollow", "Sedgemoor", "Tilbury", "Ulmstead", "Varna Bay",
            "Wolfsburg Ridge", "Yorkfield", "Zandvoort", "Aurelia", "Bellhaven", "Cragmoor", "Delmont", "Easton Weir",
            "Foxley", "Glenrock", "Hawksmoor", "Inverkeld", "Juno City", "Kingsreach", "Lochbury", "Meridian",
            "Northgate", "Old Saltmarsh", "Pinecrest", "Quarrystone", "Rookwood", "Sterling Falls", "Tempest Bay",
            "Union City", "Vanguard", "Whitecliff", "Kovarsk", "Ostrogard", "Petrovka", "Radomir", "Sarovsk", "Tverin",
            "Volkhov", "Zlatna", "Belgrava", "Cetinje Nova", "Drava", "Hvar Point", "Kordun", "Lukovo", "Mostar Ridge",
            "Novi Brod", "Prilep", "Senj", "Trogir Heights", "Vukovac", "Alcazar", "Benavente", "Castellon",
            "Durango Flats", "Esteban", "Fuentes", "Granada Vieja", "Huelma", "Ibarra", "Jaraiz", "Lorca Nueva",
            "Montoro", "Navarre", "Olvera", "Palencia", "Quesada", "Ronda Alta", "Segura", "Toledano", "Utrera",
            "Valverde", "Zafra", "Aaland", "Bergholm", "Dalsvik", "Eksjo", "Falsterbo", "Gotland Reach", "Haparanda",
            "Jorvik", "Kalmarsund", "Lulea Harbour", "Malmhaven", "Norrvik", "Oresund", "Skagen", "Tromsvik", "Uddevalla",
            "Vasterby", "Ystadt", "Aurora Springs", "Bluewater", "Cinder Hollow", "Dusk Harbor", "Echo Valley",
            "Frostmere", "Gilded Crossing", "Hollow Pines", "Iron Harbor", "Jade Hills", "Kingsfall", "Lantern Bay",
            "Midnight Ridge", "Nightfall", "Obsidian Flats", "Pale Harbor", "Quiet Hills", "Rustwater", "Shalecliff",
            "Thunder Bay", "Umber Hollow", "Vigil Point", "Wildersee", "Ashgrove", "Brimstone Valley",
        };
    }
}
