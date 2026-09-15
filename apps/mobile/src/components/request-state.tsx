import { ThemeText as Text } from "@/components/theme-text";
import { ActivityIndicator, Pressable, View } from "react-native";
import { theme, usePalette } from "@/lib/theme";
export function RequestState({
  loading,
  error,
  retry,
}: {
  loading: boolean;
  error?: Error;
  retry: () => void;
}) {
  const c = usePalette();
  return (
    <View style={{ paddingVertical: 28, gap: theme.spacing.lg }}>
      {loading ? (
        <>
          <ActivityIndicator color={c.accent} />
          <Text style={{ color: c.secondary }}>일정을 불러오는 중입니다.</Text>
        </>
      ) : (
        <>
          <Text accessibilityRole="alert" style={{ color: c.text }}>
            {error?.message ?? "아직 공개된 일정이 없습니다."}
          </Text>
          <Pressable
            accessibilityRole="button"
            onPress={retry}
            style={{
              padding: 14,
              backgroundColor: c.tint,
              borderRadius: theme.radius.button,
            }}
          >
            <Text variant="button" style={{ color: c.accent }}>
              다시 불러오기
            </Text>
          </Pressable>
        </>
      )}
    </View>
  );
}
