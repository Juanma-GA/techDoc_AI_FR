use std::{
    error::Error,
    fs,
    io::{BufRead, BufReader, Write},
    net::{SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    thread,
    time::{Duration, Instant},
};

use tauri::{LogicalSize, Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

const BACKEND_START_TIMEOUT: Duration = Duration::from_secs(20);

struct BackendProcess {
    child: Mutex<Option<Child>>,
    stopping: Arc<AtomicBool>,
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let stopping = Arc::new(AtomicBool::new(false));
            app.manage(BackendProcess {
                child: Mutex::new(None),
                stopping: Arc::clone(&stopping),
            });

            let window =
                WebviewWindowBuilder::new(app, "main", WebviewUrl::App("splash.html".into()))
                    .title("PDF Toolkit")
                    .inner_size(520.0, 380.0)
                    .decorations(true)
                    .resizable(false)
                    .center()
                    .build()?;

            let app_handle = app.handle().clone();
            thread::Builder::new()
                .name("pdf-toolkit-startup".into())
                .spawn(move || start_application(app_handle, window, stopping))?;

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to initialize PDF Toolkit")
        .run(|app, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                stop_backend(app);
            }
        });
}

fn start_application(app: tauri::AppHandle, window: WebviewWindow, stopping: Arc<AtomicBool>) {
    match start_backend(&app, &stopping) {
        Ok((child, address)) => {
            if !register_backend(&app, child) {
                return;
            }

            if stopping.load(Ordering::SeqCst) {
                return;
            }

            if let Err(error) = window.set_decorations(true) {
                log::error!("could not enable PDF Toolkit window decorations: {error}");
                show_startup_error(&window, &error.to_string());
                return;
            }
            if let Err(error) = window.set_resizable(true) {
                log::error!("could not make PDF Toolkit window resizable: {error}");
                show_startup_error(&window, &error.to_string());
                return;
            }
            if let Err(error) = window.set_min_size(Some(LogicalSize::new(800.0, 600.0))) {
                log::error!("could not set PDF Toolkit window minimum size: {error}");
                show_startup_error(&window, &error.to_string());
                return;
            }
            if let Err(error) = window.maximize() {
                log::error!("could not maximize PDF Toolkit window: {error}");
                show_startup_error(&window, &error.to_string());
                return;
            }

            match format!("http://{address}/").parse() {
                Ok(url) => {
                    if let Err(error) = window.navigate(url) {
                        log::error!("could not open PDF Toolkit interface: {error}");
                        show_startup_error(&window, &error.to_string());
                    }
                }
                Err(error) => {
                    log::error!("could not create PDF Toolkit URL: {error}");
                    show_startup_error(&window, &error.to_string());
                }
            }
        }
        Err(error) => {
            log::error!("could not start PDF Toolkit backend: {error}");
            show_startup_error(&window, &error.to_string());
        }
    }
}

fn register_backend(app: &tauri::AppHandle, mut child: Child) -> bool {
    let Some(backend) = app.try_state::<BackendProcess>() else {
        stop_child(&mut child);
        return false;
    };
    let mut child_slot = match backend.child.lock() {
        Ok(child_slot) => child_slot,
        Err(error) => {
            log::error!("could not store PDF Toolkit backend process: {error}");
            stop_child(&mut child);
            return false;
        }
    };

    if backend.stopping.load(Ordering::SeqCst) {
        stop_child(&mut child);
        return false;
    }
    *child_slot = Some(child);
    true
}

fn show_startup_error(window: &WebviewWindow, error: &str) {
    let script = format!(
        "(() => {{ const show = () => window.showStartupError({}); \
         if (document.readyState === 'loading') {{ \
           document.addEventListener('DOMContentLoaded', show, {{ once: true }}); \
         }} else {{ show(); }} }})();",
        javascript_string_literal(error)
    );
    if let Err(eval_error) = window.eval(script) {
        log::error!("could not display PDF Toolkit startup error: {eval_error}");
    }
}

fn javascript_string_literal(value: &str) -> String {
    let mut literal = String::from("\"");
    for character in value.chars() {
        match character {
            '\\' => literal.push_str("\\\\"),
            '"' => literal.push_str("\\\""),
            '\n' => literal.push_str("\\n"),
            '\r' => literal.push_str("\\r"),
            '\t' => literal.push_str("\\t"),
            '\u{2028}' => literal.push_str("\\u2028"),
            '\u{2029}' => literal.push_str("\\u2029"),
            character if character.is_control() => {
                use std::fmt::Write as _;
                let _ = write!(literal, "\\u{:04x}", character as u32);
            }
            character => literal.push(character),
        }
    }
    literal.push('"');
    literal
}

fn start_backend(
    app: &tauri::AppHandle,
    stopping: &AtomicBool,
) -> Result<(Child, SocketAddr), Box<dyn Error>> {
    let executable_name = if cfg!(windows) {
        "pdf-toolkit-backend.exe"
    } else {
        "pdf-toolkit-backend"
    };
    let executable = if cfg!(debug_assertions) {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../backend/bin")
            .join(executable_name)
    } else {
        app.path().resource_dir()?.join(executable_name)
    };
    if !executable.is_file() {
        return Err(format!("PDF Toolkit backend not found: {}", executable.display()).into());
    }

    let data_dir = app.path().app_local_data_dir()?;
    fs::create_dir_all(&data_dir)?;
    let ready_file = data_dir.join(format!(
        "pdf-toolkit-{}-{}.address",
        std::process::id(),
        app.config().identifier
    ));
    match fs::remove_file(&ready_file) {
        Ok(()) => {}
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
        Err(error) => return Err(error.into()),
    }

    let mut command = Command::new(executable);
    command
        .env("PDF_TOOLKIT_ADDR", "127.0.0.1:0")
        .env("PDF_TOOLKIT_READY_FILE", &ready_file)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    let mut child = command.spawn()?;

    match wait_for_backend(&mut child, &ready_file, stopping) {
        Ok(address) => {
            remove_ready_file(&ready_file);
            Ok((child, address))
        }
        Err(error) => {
            if let Err(kill_error) = child.kill() {
                log::warn!("could not stop backend after startup failure: {kill_error}");
            }
            if let Err(wait_error) = child.wait() {
                log::warn!("could not reap backend after startup failure: {wait_error}");
            }
            remove_ready_file(&ready_file);
            Err(error)
        }
    }
}

fn wait_for_backend(
    child: &mut Child,
    ready_file: &Path,
    stopping: &AtomicBool,
) -> Result<SocketAddr, Box<dyn Error>> {
    let deadline = Instant::now() + BACKEND_START_TIMEOUT;
    loop {
        if stopping.load(Ordering::SeqCst) {
            return Err("PDF Toolkit startup was cancelled".into());
        }
        if let Some(status) = child.try_wait()? {
            return Err(format!("PDF Toolkit backend exited during startup: {status}").into());
        }

        match fs::read_to_string(ready_file) {
            Ok(contents) => {
                let address: SocketAddr = contents.trim().parse()?;
                if !address.ip().is_loopback() || address.port() == 0 {
                    return Err("PDF Toolkit backend reported an unsafe address".into());
                }
                if backend_is_healthy(address) {
                    return Ok(address);
                }
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(error) => return Err(error.into()),
        }

        if Instant::now() >= deadline {
            return Err("PDF Toolkit backend did not become ready in time".into());
        }
        thread::sleep(Duration::from_millis(100));
    }
}

fn backend_is_healthy(address: SocketAddr) -> bool {
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(500)) else {
        return false;
    };
    if stream
        .set_read_timeout(Some(Duration::from_millis(500)))
        .is_err()
    {
        return false;
    }
    if stream
        .write_all(
            format!("GET /api/v1/health HTTP/1.1\r\nHost: {address}\r\nConnection: close\r\n\r\n")
                .as_bytes(),
        )
        .is_err()
    {
        return false;
    }

    let mut status = String::new();
    BufReader::new(stream).read_line(&mut status).is_ok() && status.starts_with("HTTP/1.1 200 ")
}

fn remove_ready_file(path: &Path) {
    if let Err(error) = fs::remove_file(path) {
        if error.kind() != std::io::ErrorKind::NotFound {
            log::warn!("could not remove backend readiness file: {error}");
        }
    }
}

fn stop_backend(app: &tauri::AppHandle) {
    let Some(backend) = app.try_state::<BackendProcess>() else {
        return;
    };
    backend.stopping.store(true, Ordering::SeqCst);
    let mut child_slot = match backend.child.lock() {
        Ok(child) => child,
        Err(error) => {
            log::error!("could not access PDF Toolkit backend process: {error}");
            return;
        }
    };
    let Some(mut child) = child_slot.take() else {
        return;
    };
    stop_child(&mut child);
}

fn stop_child(child: &mut Child) {
    match child.try_wait() {
        Ok(Some(_)) => return,
        Ok(None) => {}
        Err(error) => {
            log::error!("could not inspect PDF Toolkit backend process: {error}");
            return;
        }
    }
    if let Err(error) = child.kill() {
        log::error!("could not stop PDF Toolkit backend: {error}");
        return;
    }
    if let Err(error) = child.wait() {
        log::error!("could not wait for PDF Toolkit backend to stop: {error}");
    }
}
