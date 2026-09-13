// Local demonstration fixtures. They are never published to the OROT server.
export type DemoRelease = {
  id: number;
  title: string;
  artist_name: string;
  variant: string;
  preorder_opens_at: string | null;
  release_date: string | null;
  updated_at: string;
  color: string;
};
export const demoReleases: readonly DemoRelease[] = [
  {
    id: 1,
    title: "느린 오후",
    artist_name: "OROT 스튜디오",
    variant: "180g · 크림 컬러 LP",
    preorder_opens_at: "2026-09-18T05:00:00Z",
    release_date: "2026-10-02",
    updated_at: "2026-09-12T03:00:00Z",
    color: "#B45737",
  },
  {
    id: 2,
    title: "밤의 가장자리",
    artist_name: "작은 파동",
    variant: "블랙 바이닐 · 1LP",
    preorder_opens_at: "2026-09-22T09:00:00Z",
    release_date: "2026-10-16",
    updated_at: "2026-09-13T03:00:00Z",
    color: "#516D64",
  },
  {
    id: 3,
    title: "아직 오지 않은 계절",
    artist_name: "여름의 기록",
    variant: "한정반 · 2LP",
    preorder_opens_at: null,
    release_date: null,
    updated_at: "2026-09-11T03:00:00Z",
    color: "#746080",
  },
];
export type FeedSort = "imminent" | "recent";
export function sortDemoReleases(sort: FeedSort): DemoRelease[] {
  return [...demoReleases].sort((a, b) => {
    if (sort === "recent")
      return Date.parse(b.updated_at) - Date.parse(a.updated_at);
    const time = (r: DemoRelease) =>
      r.preorder_opens_at ? Date.parse(r.preorder_opens_at) : Infinity;
    return time(a) - time(b) || a.id - b.id;
  });
}
export function findDemoRelease(id: string | undefined) {
  if (!id || !/^[1-9]\d*$/.test(id)) return undefined;
  return demoReleases.find((release) => String(release.id) === id);
}
