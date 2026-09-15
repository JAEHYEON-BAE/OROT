import { ThemeText as Text } from "@/components/theme-text";
import { Tabs } from "expo-router";
import { theme, usePalette } from "@/lib/theme";

export default function TabsLayout() {
  const colors = usePalette();
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarLabelStyle: theme.typography.caption,
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
            <Text variant="tabIcon" style={{ color }}>
              {theme.icons.feed}
            </Text>
          ),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: "설정",
          tabBarIcon: ({ color }) => (
            <Text variant="tabIcon" style={{ color }}>
              {theme.icons.settings}
            </Text>
          ),
        }}
      />
    </Tabs>
  );
}
