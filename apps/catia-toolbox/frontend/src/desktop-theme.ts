type NativeTheme = "dark" | "light";

type NativeWindow = {
  setTheme: (theme: NativeTheme) => Promise<void>;
};

type TauriGlobal = {
  window?: {
    getCurrentWindow?: () => NativeWindow;
  };
};

const nativeWindow = (window as Window & { __TAURI__?: TauriGlobal })
  .__TAURI__?.window?.getCurrentWindow?.();

if (nativeWindow) {
  const synchronizeTheme = () => {
    const theme: NativeTheme = document.documentElement.classList.contains("dark")
      ? "dark"
      : "light";
    void nativeWindow.setTheme(theme).catch((error: unknown) => {
      console.error("Unable to synchronize desktop window theme:", error);
    });
  };

  const observer = new MutationObserver(synchronizeTheme);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  synchronizeTheme();
}