import { Text, type TextProps } from "react-native";
import { theme, usePalette, type TextVariant } from "@/lib/theme";

/** 기본 본문 글꼴을 빠뜨리지 않으며 OS의 글자 확대 설정을 그대로 따릅니다. */
export function ThemeText({
  variant = "body",
  style,
  ...props
}: TextProps & { variant?: TextVariant }) {
  const colors = usePalette();
  return (
    <Text
      {...props}
      style={[theme.typography[variant], { color: colors.text }, style]}
    />
  );
}
