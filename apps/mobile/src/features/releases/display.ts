export function formatPreorder(value: string | null | undefined): string {
  if (!value) return "예약 일정 미정";
  return (
    new Intl.DateTimeFormat("ko-KR", {
      timeZone: "Asia/Seoul",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date(value)) + " KST"
  );
}
export function formatReleaseDate(value: string | null | undefined): string {
  if (!value) return "발매일 미정";
  const [year, month, day] = value.split("-");
  return `${year}년 ${Number(month)}월 ${Number(day)}일`;
}
