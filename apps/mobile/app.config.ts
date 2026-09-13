import type { ExpoConfig } from "expo/config";

// This first milestone contains demonstration data only. Prevent store builds.
if (process.env.EAS_BUILD_PROFILE === "production") {
  throw new Error(
    "T-033 mock scaffold is not ready for production distribution.",
  );
}

const config: ExpoConfig = {
  name: "OROT",
  slug: "orot",
  version: "0.1.0",
  scheme: "orot-dev",
  orientation: "portrait",
  userInterfaceStyle: "automatic",
  icon: "./assets/icon.png",
  ios: { bundleIdentifier: "com.orot.mobile.dev", supportsTablet: false },
  android: { package: "com.orot.mobile.dev" },
  plugins: [
    "expo-router",
    ["expo-splash-screen", { backgroundColor: "#F7F4ED" }],
  ],
  experiments: { typedRoutes: true },
};

export default config;
