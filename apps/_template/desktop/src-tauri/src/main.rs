#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;
mod health;

use std::sync::atomic::Ordering;
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};

fn main() {
    tauri::Builder::default()
        .manage(backend::Backend::default())
        .setup(|app| {
            let window = WebviewWindowBuilder::new(
                app,
                "main",
                WebviewUrl::App("src/desktop-startup.html".into()),
            )
            .title(
                app.config()
                    .product_name
                    .clone()
                    .unwrap_or_else(|| "Desktop".into()),
            )
            .inner_size(1200.0, 800.0)
            .theme(Some(tauri::Theme::Dark))
            .build()?;
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                if let Err(error) = backend::start(&handle, &window) {
                    eprintln!("Desktop startup failed: {error}");
                    backend::stop(&handle);
                    let text = serde_json::to_string(&format!("Startup failed: {error}"))
                        .expect("strings are JSON serializable");
                    if let Err(error) = window.eval(format!(
                        "(() => {{ const show = () => {{ \
                           const status = document.getElementById('status'); \
                           if (status) {{ status.textContent = {text}; status.hidden = false; }} \
                           const loading = document.getElementById('startup-loading'); \
                           if (loading) loading.hidden = true; }}; \
                         if (document.readyState === 'loading') {{ \
                           document.addEventListener('DOMContentLoaded', show, {{once:true}}); \
                         }} else {{ show(); }} }})();"
                    )) {
                        eprintln!("Could not show startup error: {error}");
                    }
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("could not initialize desktop application")
        .run(|app, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                app.state::<backend::Backend>()
                    .stopping
                    .store(true, Ordering::SeqCst);
                backend::stop(app);
            }
        });
}
