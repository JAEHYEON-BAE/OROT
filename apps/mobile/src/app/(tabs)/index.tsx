import { ThemeText as Text } from "@/components/theme-text";
import { useState } from "react";
import { FlatList, Pressable, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Link } from "expo-router";
import { RecordArt } from "@/components/record-art";
import { formatSchedule } from "@/features/releases/display";
import { getFeed, type FeedSort } from "@/lib/api/client";
import { useResource } from "@/lib/api/use-resource";
import { RequestState } from "@/components/request-state";
import { theme, usePalette } from "@/lib/theme";

export default function FeedScreen() {
  const colors = usePalette();
  const [sort, setSort] = useState<FeedSort>("imminent");
  const feed = useResource(`feed:${sort}`, (signal) => getFeed(sort, signal));
  return (
    <SafeAreaView
      edges={["top", "left", "right"]}
      style={{ flex: 1, backgroundColor: colors.background }}
    >
      <FlatList
        contentContainerStyle={styles.content}
        data={feed.data?.items.map((item) => item.release) ?? []}
        refreshing={feed.loading && !!feed.data}
        onRefresh={feed.refresh}
        ListEmptyComponent={
          <RequestState
            loading={feed.loading}
            error={feed.error}
            retry={feed.refresh}
          />
        }
        keyExtractor={(item) => String(item.id)}
        ListHeaderComponent={
          <View>
            <View style={styles.brandRow}>
              <Text style={[styles.brand, { color: colors.text }]}>OROT</Text>
              <Text style={[styles.eyebrow, { color: colors.secondary }]}>
                음악을 기다리는 시간
              </Text>
            </View>
            <Text
              accessibilityRole="header"
              style={[styles.heading, { color: colors.text }]}
            >
              다음 한 장을{"\n"}기다리는 마음.
            </Text>
            <Text style={[styles.intro, { color: colors.secondary }]}>
              새로운 음반과 예약 일정을 한곳에서 만나세요.
            </Text>
            <View style={[styles.notice, { backgroundColor: colors.tint }]}>
              <Text style={[theme.typography.label, { color: colors.accent }]}>
                OROT의 최신 공개 일정 · 한국 시간 기준
              </Text>
            </View>
            <View style={styles.filters}>
              {(["imminent", "recent"] as const).map((value) => (
                <Pressable
                  key={value}
                  accessibilityRole="button"
                  accessibilityState={{ selected: sort === value }}
                  onPress={() => setSort(value)}
                  style={[
                    styles.filter,
                    {
                      backgroundColor:
                        sort === value ? colors.text : colors.surface,
                      borderColor: colors.border,
                    },
                  ]}
                >
                  <Text
                    style={{
                      color: sort === value ? colors.background : colors.text,
                      ...theme.typography.button,
                    }}
                  >
                    {value === "imminent" ? "발매 임박순" : "최근 변경순"}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
        }
        renderItem={({ item }) => (
          <Link
            href={{ pathname: "/releases/[id]", params: { id: item.id } }}
            asChild
          >
            <Pressable
              accessibilityRole="link"
              accessibilityLabel={`${item.title}, ${item.artist_name ?? "아티스트 미정"}, 상세 보기`}
              style={StyleSheet.flatten([
                styles.card,
                { backgroundColor: colors.surface, borderColor: colors.border },
              ])}
            >
              <RecordArt uri={item.cover_url} />
              <View style={styles.cardText}>
                <Text style={[styles.artist, { color: colors.secondary }]}>
                  {item.artist_name ?? "아티스트 미정"}
                </Text>
                <Text style={[styles.title, { color: colors.text }]}>
                  {item.title}
                </Text>
                <Text style={[styles.variant, { color: colors.secondary }]}>
                  {item.variant ?? item.format ?? "판본 정보 미정"}
                </Text>
                <Text style={[styles.time, { color: colors.accent }]}>
                  {formatSchedule(item)}
                </Text>
              </View>
            </Pressable>
          </Link>
        )}
        ListFooterComponent={
          <Text style={[styles.footer, { color: colors.secondary }]}>
            좋아하는 음악을, 놓치지 않도록.
          </Text>
        }
      />
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  content: { padding: theme.layout.feedPadding, paddingBottom: 30 },
  brandRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    justifyContent: "space-between",
    gap: theme.spacing.sm,
    marginBottom: 30,
  },
  brand: theme.typography.brand,
  eyebrow: theme.typography.caption,
  heading: {
    ...theme.typography.hero,
    marginBottom: theme.spacing.md,
  },
  intro: theme.typography.intro,
  notice: {
    padding: theme.spacing.md,
    borderRadius: theme.radius.notice,
    marginTop: 22,
    marginBottom: 22,
  },
  filters: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.sm,
    marginBottom: 18,
  },
  filter: {
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: 13,
    borderRadius: theme.radius.pill,
    borderWidth: 1,
  },
  card: {
    flexDirection: "row",
    alignItems: "center",
    padding: 15,
    borderRadius: theme.radius.card,
    borderWidth: 1,
    gap: 14,
    marginBottom: theme.spacing.md,
  },
  cardText: { flex: 1, gap: 5 },
  artist: theme.typography.caption,
  title: theme.typography.cardTitle,
  variant: theme.typography.caption,
  time: { ...theme.typography.captionStrong, marginTop: theme.spacing.xs },
  footer: { ...theme.typography.caption, textAlign: "center", marginTop: 18 },
});
