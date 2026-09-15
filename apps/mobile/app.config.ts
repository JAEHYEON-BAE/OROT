import type { ExpoConfig } from "expo/config";
import { theme } from "./theme.ts";

// Store signing and mobile push are not configured yet. Prevent accidental distribution.
if (process.env.EAS_BUILD_PROFILE === "production") {
  throw new Error(
    "OROT development app is not ready for production distribution.",
  );
}

const config: ExpoConfig = {
  name: "OROT",
  slug: "orot",
  version: "0.1.0",
  scheme: "orot-dev",
  orientation: "portrait",
  userInterfaceStyle: "automatic",
  icon: theme.images.appIcon,
  ios: { bundleIdentifier: "com.orot.mobile.dev", supportsTablet: false },
  android: { package: "com.orot.mobile.dev" },
  plugins: [
    "expo-router",
    [
      "expo-splash-screen",
      {
        backgroundColor: theme.colors.light.background,
        dark: { backgroundColor: theme.colors.dark.background },
      },
    ],
    ...(theme.fonts.files.length
      ? [
          ["expo-font", { fonts: theme.fonts.files }] as [
            string,
            { fonts: string[] },
          ],
        ]
      : []),
  ],
  experiments: { typedRoutes: true },
};

export default config;
