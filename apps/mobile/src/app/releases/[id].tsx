import { Link, useLocalSearchParams } from "expo-router";
import { ScrollView, StyleSheet, Text, View, Linking, Pressable, Alert } from "react-native";
import { RecordArt } from "@/components/record-art";
import { formatPreorder, formatReleaseDate } from "@/features/releases/display";
import { getRelease, ApiError, sellerUrl } from "@/lib/api/client";
import { useResource } from "@/lib/api/use-resource";
import { RequestState } from "@/components/request-state";
import { usePalette } from "@/lib/theme";

export default function DetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const resource = useResource(`release:${id}`, signal => getRelease(id ?? "", signal));
  const release = resource.data;
  const colors = usePalette();
  if (resource.loading || (resource.error && !(resource.error instanceof ApiError && resource.error.status === 404))) return <View style={styles.content}><RequestState loading={resource.loading} error={resource.error} retry={resource.refresh} /></View>;
  if (!release)
    return (
      <View style={styles.content}>
        <Text
          accessibilityRole="header"
          style={[styles.title, { color: colors.text }]}
        >
          일정을 찾을 수 없습니다.
        </Text>
        <Link href="/" style={{ color: colors.accent, paddingVertical: 20 }}>
          발매 목록으로 돌아가기
        </Link>
      </View>
    );
  return (
    <ScrollView contentContainerStyle={styles.content}>
      <RecordArt large color="#516D64" />
      <Text style={[styles.artist, { color: colors.secondary }]}>
        {release.artist_name ?? "아티스트 미정"}
      </Text>
      <Text
        accessibilityRole="header"
        style={[styles.title, { color: colors.text }]}
      >
        {release.title}
      </Text>
      <Text style={[styles.body, { color: colors.secondary }]}>
        {release.variant ?? release.format ?? "판본 정보 미정"}
      </Text>
      <View style={[styles.card, { backgroundColor: colors.surface }]}>
        <Text style={[styles.label, { color: colors.secondary }]}>
          예약 시작
        </Text>
        <Text style={[styles.value, { color: colors.text }]}>
          {formatPreorder(release.preorder_opens_at)}
        </Text>
        <Text style={[styles.label, { color: colors.secondary }]}>발매일</Text>
        <Text style={[styles.value, { color: colors.text }]}>
          {formatReleaseDate(release.release_date)}
        </Text>
      </View>
      <Text accessibilityRole="header" style={[styles.value, { color: colors.text }]}>판매처</Text>
      {(release.links ?? []).length === 0 && <Text style={[styles.body, { color: colors.secondary }]}>아직 등록된 판매처가 없습니다.</Text>}
      {(release.links ?? []).map(link => {
        const url = sellerUrl(link.url);
        return <Pressable key={link.id} disabled={!url} accessibilityRole="link" accessibilityState={{ disabled: !url }} onPress={() => { if (url) void Linking.openURL(url).catch(() => Alert.alert("링크를 열 수 없습니다.", "잠시 후 다시 시도해주세요.")); }} style={[styles.card, { backgroundColor: colors.surface }]}>
          <Text style={[styles.value, { color: colors.accent }]}>{link.shop_name} ↗</Text>
          <Text style={[styles.body, { color: colors.secondary }]}>{link.price_krw == null ? "가격은 판매처에서 확인해주세요." : `${link.price_krw.toLocaleString("ko-KR")}원`}</Text>
        </Pressable>;
      })}
    </ScrollView>
  );
}
const styles = StyleSheet.create({
  content: { padding: 24, paddingBottom: 48 },
  artist: { fontSize: 15, marginTop: 24, marginBottom: 8 },
  title: { fontSize: 29, fontWeight: "700", marginBottom: 10 },
  body: { fontSize: 15, lineHeight: 25 },
  card: { padding: 20, borderRadius: 16, marginVertical: 24 },
  label: { fontSize: 13, marginBottom: 6 },
  value: { fontSize: 17, fontWeight: "600", marginBottom: 18 },
});
