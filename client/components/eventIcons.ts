import { CloudHail, CloudRain, Flame, Mountain, Waves } from "lucide-react";

export const EVENT_ICON: Record<string, any> = {
  hail: CloudHail, inundation: Waves, cloudburst: CloudRain, landslide: Mountain, natural_fire: Flame,
  unseasonal_rain_post_harvest: CloudRain, other: CloudRain,
};
