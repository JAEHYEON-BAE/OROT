import { StyleSheet, View } from "react-native";

export function RecordArt({
  color,
  large = false,
}: {
  color: string;
  large?: boolean;
}) {
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[styles.cover, { backgroundColor: color }, large && styles.large]}
    >
      <View style={styles.disc}>
        <View style={styles.groove}>
          <View style={[styles.label, { backgroundColor: color }]}>
            <View style={styles.hole} />
          </View>
        </View>
      </View>
    </View>
  );
}
const styles = StyleSheet.create({
  cover: {
    width: 72,
    height: 80,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  large: { width: "100%", height: 230, borderRadius: 18 },
  disc: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: "#242723",
    alignItems: "center",
    justifyContent: "center",
  },
  groove: {
    width: 46,
    height: 46,
    borderRadius: 23,
    borderWidth: 1,
    borderColor: "#61635C",
    alignItems: "center",
    justifyContent: "center",
  },
  label: {
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: "center",
    justifyContent: "center",
  },
  hole: { width: 5, height: 5, borderRadius: 3, backgroundColor: "#F7F4ED" },
});
