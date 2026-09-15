import { ThemeText as Text } from "@/components/theme-text";
import { ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { theme, usePalette } from "@/lib/theme";

export default function SettingsScreen() {
  const colors = usePalette();
  return (
    <SafeAreaView
      edges={["top", "left", "right"]}
      style={{ flex: 1, backgroundColor: colors.background }}
    >
      <ScrollView contentContainerStyle={styles.content}>
        <Text
          accessibilityRole="header"
          style={[styles.heading, { color: colors.text }]}
        >
          설정
        </Text>
        <View style={[styles.card, { backgroundColor: colors.surface }]}>
          <Text style={[styles.title, { color: colors.text }]}>일정 알림</Text>
          <Text style={[styles.body, { color: colors.secondary }]}>
            모바일 알림은 준비 중입니다. 현재 앱에서는 알림 권한을 요청하거나
            구독을 등록하지 않습니다.
          </Text>
        </View>
        <View style={[styles.card, { backgroundColor: colors.surface }]}>
          <Text style={[styles.title, { color: colors.text }]}>OROT</Text>
          <Text style={[styles.body, { color: colors.secondary }]}>
            버전 0.1.0 · 웹 서비스 연결{"\n"}실제 발매 정보와 연결되지 않은
            화면입니다.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  content: { padding: theme.layout.screenPadding },
  heading: { ...theme.typography.screenTitle, marginBottom: 28 },
  card: {
    padding: 20,
    borderRadius: theme.radius.card,
    marginBottom: theme.spacing.lg,
  },
  title: { ...theme.typography.sectionTitle, marginBottom: theme.spacing.md },
  body: theme.typography.body,
});
