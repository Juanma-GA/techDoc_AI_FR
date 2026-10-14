use std::{
    error::Error,
    fs,
    io::{BufRead, BufReader, Write},
    net::{SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};

use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};

const BACKEND_START_TIMEOUT: Duration = Duration::from_secs(20);

struct BackendProcess(Mutex<Child>);

pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let (child, address) = start_backend(app.handle())?;
            app.manage(BackendProcess(Mutex::new(child)));

            WebviewWindowBuilder::new(
                app,
                "main",
                WebviewUrl::External(format!("http://{address}/").parse()?),
            )
            .title("PDF Toolkit")
            .inner_size(1180.0, 800.0)
            .min_inner_size(800.0, 600.0)
            .build()?;

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

fn start_backend(app: &tauri::AppHandle) -> Result<(Child, SocketAddr), Box<dyn Error>> {
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

    match wait_for_backend(&mut child, &ready_file) {
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

fn wait_for_backend(child: &mut Child, ready_file: &Path) -> Result<SocketAddr, Box<dyn Error>> {
    let deadline = Instant::now() + BACKEND_START_TIMEOUT;
    loop {
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
            format!(
                "GET /api/v1/health HTTP/1.1\r\nHost: {address}\r\nConnection: close\r\n\r\n"
            )
            .as_bytes(),
        )
        .is_err()
    {
        return false;
    }

    let mut status = String::new();
    BufReader::new(stream)
        .read_line(&mut status)
        .is_ok()
        && status.starts_with("HTTP/1.1 200 ")
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
    let mut child = match backend.0.lock() {
        Ok(child) => child,
        Err(error) => {
            log::error!("could not access PDF Toolkit backend process: {error}");
            return;
        }
    };
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
