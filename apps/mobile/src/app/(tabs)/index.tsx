import { useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Link } from "expo-router";
import { RecordArt } from "@/components/record-art";
import { formatPreorder, formatReleaseDate } from "@/features/releases/display";
import { getFeed, type FeedSort } from "@/lib/api/client";
import { useResource } from "@/lib/api/use-resource";
import { RequestState } from "@/components/request-state";
import { usePalette } from "@/lib/theme";

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
        data={feed.data?.items.map(item => item.release) ?? []}
        refreshing={feed.loading && !!feed.data}
        onRefresh={feed.refresh}
        ListEmptyComponent={<RequestState loading={feed.loading} error={feed.error} retry={feed.refresh} />}
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
              <Text style={{ color: colors.accent, fontSize: 13 }}>
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
                      fontWeight: "600",
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
              <RecordArt color="#516D64" />
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
                  {item.preorder_opens_at ? formatPreorder(item.preorder_opens_at) : formatReleaseDate(item.release_date)}
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
  content: { padding: 22, paddingBottom: 30 },
  brandRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
    marginBottom: 30,
  },
  brand: { fontSize: 27, fontWeight: "800", letterSpacing: 4 },
  eyebrow: { fontSize: 12 },
  heading: {
    fontSize: 32,
    lineHeight: 43,
    fontWeight: "700",
    marginBottom: 12,
  },
  intro: { fontSize: 14, lineHeight: 23 },
  notice: { padding: 12, borderRadius: 10, marginTop: 22, marginBottom: 22 },
  filters: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 18 },
  filter: {
    paddingHorizontal: 16,
    paddingVertical: 13,
    borderRadius: 24,
    borderWidth: 1,
  },
  card: {
    flexDirection: "row",
    alignItems: "center",
    padding: 15,
    borderRadius: 16,
    borderWidth: 1,
    gap: 14,
    marginBottom: 12,
  },
  cardText: { flex: 1, gap: 5 },
  artist: { fontSize: 12 },
  title: { fontSize: 18, fontWeight: "700" },
  variant: { fontSize: 12 },
  time: { fontSize: 12, fontWeight: "600", marginTop: 4 },
  footer: { textAlign: "center", fontSize: 12, marginTop: 18 },
});
