import { Tabs } from "expo-router";
import { Text } from "react-native";
import { usePalette } from "@/lib/theme";

export default function TabsLayout() {
  const colors = usePalette();
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.secondary,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "발매 일정",
          tabBarIcon: ({ color }) => (
            <Text style={{ color, fontSize: 22 }}>◉</Text>
          ),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: "설정",
          tabBarIcon: ({ color }) => (
            <Text style={{ color, fontSize: 22 }}>☷</Text>
          ),
        }}
      />
    </Tabs>
  );
}
