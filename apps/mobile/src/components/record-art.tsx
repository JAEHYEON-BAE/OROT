import { useState } from "react";
import { Image, StyleSheet, View } from "react-native";
import { theme, usePalette } from "@/lib/theme";

const placeholder = theme.images.recordPlaceholder();

export function RecordArt({
  color,
  uri,
  large = false,
}: {
  color?: string;
  uri?: string | null;
  large?: boolean;
}) {
  const colors = usePalette();
  const coverColor = color ?? colors.recordCover;
  const [failedUri, setFailedUri] = useState<string>();
  const [placeholderFailed, setPlaceholderFailed] = useState(false);
  const showCover = !!uri && uri !== failedUri && /^https?:\/\//.test(uri);
  const source = showCover
    ? { uri }
    : placeholderFailed
      ? undefined
      : placeholder;
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[
        styles.cover,
        { backgroundColor: coverColor },
        large && styles.large,
      ]}
    >
      {source ? (
        <Image
          source={source}
          resizeMode="contain"
          onError={() =>
            showCover ? setFailedUri(uri) : setPlaceholderFailed(true)
          }
          style={styles.image}
        />
      ) : (
        <View style={[styles.disc, { backgroundColor: colors.recordDisc }]}>
          <View style={[styles.groove, { borderColor: colors.recordGroove }]}>
            <View style={[styles.label, { backgroundColor: coverColor }]}>
              <View
                style={[styles.hole, { backgroundColor: colors.recordHole }]}
              />
            </View>
          </View>
        </View>
      )}
    </View>
  );
}
const art = theme.recordArt;
const styles = StyleSheet.create({
  cover: {
    width: art.thumbnailWidth,
    height: art.thumbnailHeight,
    borderRadius: theme.radius.small,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  image: { width: "100%", height: "100%" },
  large: {
    width: "100%",
    height: art.detailHeight,
    borderRadius: theme.radius.cover,
  },
  disc: {
    width: art.disc,
    height: art.disc,
    borderRadius: theme.radius.circle,
    alignItems: "center",
    justifyContent: "center",
  },
  groove: {
    width: art.groove,
    height: art.groove,
    borderRadius: theme.radius.circle,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  label: {
    width: art.label,
    height: art.label,
    borderRadius: theme.radius.circle,
    alignItems: "center",
    justifyContent: "center",
  },
  hole: {
    width: art.hole,
    height: art.hole,
    borderRadius: theme.radius.circle,
  },
});
