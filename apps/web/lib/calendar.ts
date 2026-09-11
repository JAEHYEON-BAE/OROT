const KST = "Asia/Seoul";

/** Parse the selected month without converting KST midnight to the server timezone. */
export function calendarMonth(month: string | string[] | undefined, today: Date) {
  const fallback = today.toLocaleDateString("en-CA", { timeZone: KST }).slice(0, 7);
  const valid = typeof month === "string" && /^(?:[1-9]\d{3})-(?:0[1-9]|1[0-2])$/.test(month);
  const [year, value] = (valid ? month : fallback).split("-").map(Number);
  return { year, monthIndex: value - 1 };
}
