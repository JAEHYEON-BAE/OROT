import { useColorScheme } from "react-native";
import { theme } from "../../theme";
export { theme } from "../../theme";
export type { Palette, TextVariant } from "../../theme";

export function usePalette() {
  return useColorScheme() === "dark" ? theme.colors.dark : theme.colors.light;
}
