export type UniverseDepth = 'far' | 'mid' | 'near';

export type TrajectoryType = 
  | 'diag-a'
  | 'diag-b'
  | 'vertical-wave'
  | 'shallow-curve-left'
  | 'shallow-curve-right'
  | 'depth-journey';

export interface PublicBotServer {
  id: string;
  name: string;
  icon?: string | null;
  memberCount: number;
  isPartner?: boolean;
  isVerified?: boolean;
  isCommunity?: boolean;
}

export interface FloatingServerSlot {
  id: string;
  depth: UniverseDepth;
  trajectory: TrajectoryType;
  baseX: number; // 0 to 100 (% of container width)
  baseY: number; // 0 to 100 (% of container height)
  duration: number; // seconds
  delay: number; // negative seconds for immediate stagger
  accentColor?: string;
  hideOnMobile?: boolean;
  hideOnTablet?: boolean;
}

export interface FloatingServerNode {
  slot: FloatingServerSlot;
  server: PublicBotServer;
}
