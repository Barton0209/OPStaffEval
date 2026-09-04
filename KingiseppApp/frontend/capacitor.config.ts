import { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "ru.kingisepp.ocenka",
  appName: "Оценка ОП",
  webDir: "dist",
  server: {
    androidScheme: "https",
    cleartext: false,
  },
  android: {
    allowMixedContent: false,
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 800,
      backgroundColor: "#0d3b2e",
    },
  },
};

export default config;
