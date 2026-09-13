import { useColorScheme } from "react-native";

const light = {
  background: "#F7F4ED",
  surface: "#FFFFFF",
  text: "#222820",
  secondary: "#62675D",
  border: "#DEDCD3",
  accent: "#A44420",
  tint: "#F5E5D9",
};
const dark: typeof light = {
  background: "#171C18",
  surface: "#242B25",
  text: "#F5F2E9",
  secondary: "#BCC4B8",
  border: "#3E473D",
  accent: "#F1AA80",
  tint: "#413025",
};
export function usePalette() {
  return useColorScheme() === "dark" ? dark : light;
}
