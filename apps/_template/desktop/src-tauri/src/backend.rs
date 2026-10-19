use crate::health::healthy;
use serde::Deserialize;
use std::{
    error::Error,
    net::TcpListener,
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Mutex,
    },
    thread,
    time::{Duration, Instant},
};
use tauri::{Manager, WebviewWindow};

type Result<T> = std::result::Result<T, Box<dyn Error>>;

#[derive(Default)]
pub struct Backend {
    child: Mutex<Option<Child>>,
    pub stopping: AtomicBool,
}

#[derive(Deserialize)]
struct Spec {
    executable: String,
    cwd: String,
    root: String,
    slug: String,
    args: Vec<String>,
    bootstrap: Vec<Vec<String>>,
}

pub fn start(app: &tauri::AppHandle, window: &WebviewWindow) -> Result<()> {
    let spec: Spec = serde_json::from_str(include_str!("../runtime.json"))?;
    let root = if spec.root.is_empty() {
        app.path().resource_dir()?
    } else {
        PathBuf::from(&spec.root)
    };
    let data = app.path().app_local_data_dir()?;
    std::fs::create_dir_all(data.join("storage"))?;
    let address = TcpListener::bind("127.0.0.1:0")?.local_addr()?;
    let database = format!(
        "sqlite:///{}",
        data.join(format!("{}.db", spec.slug)).display()
    )
    .replace('\\', "/");
    let make_command = |args: &[String]| {
        let mut command = Command::new(root.join(&spec.executable));
        command
            .current_dir(root.join(&spec.cwd))
            .args(
                args.iter()
                    .map(|arg| arg.replace("{port}", &address.port().to_string())),
            )
            .env("DATABASE_URL", &database)
            .env("STORAGE_DIR", data.join("storage"))
            .env("BIND_HOST", "127.0.0.1")
            .stdin(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        command
    };
    for args in &spec.bootstrap {
        register(app, make_command(args).spawn()?)?;
        let deadline = Instant::now() + Duration::from_secs(60);
        loop {
            if app.state::<Backend>().stopping.load(Ordering::SeqCst) {
                return Err("Startup cancelled".into());
            }
            let state = app.state::<Backend>();
            let mut slot = state.child.lock().map_err(|e| e.to_string())?;
            if let Some(status) = slot.as_mut().ok_or("Bootstrap stopped")?.try_wait()? {
                *slot = None;
                if !status.success() {
                    return Err(format!("Bootstrap failed: {status}").into());
                }
                break;
            }
            drop(slot);
            if Instant::now() >= deadline {
                return Err("Bootstrap timed out".into());
            }
            thread::sleep(Duration::from_millis(100));
        }
    }
    register(app, make_command(&spec.args).spawn()?)?;
    let deadline = Instant::now() + Duration::from_secs(30);
    loop {
        let state = app.state::<Backend>();
        if state.stopping.load(Ordering::SeqCst) {
            return Err("Startup cancelled".into());
        }
        {
            let mut slot = state.child.lock().map_err(|e| e.to_string())?;
            if let Some(status) = slot.as_mut().ok_or("Backend stopped")?.try_wait()? {
                return Err(format!("Backend exited: {status}").into());
            }
        }
        if healthy(address) {
            window.navigate(format!("http://{address}/").parse()?)?;
            return Ok(());
        }
        if Instant::now() >= deadline {
            return Err("Backend health check timed out".into());
        }
        thread::sleep(Duration::from_millis(100));
    }
}

fn register(app: &tauri::AppHandle, mut child: Child) -> Result<()> {
    let state = app.state::<Backend>();
    let mut slot = match state.child.lock() {
        Ok(slot) => slot,
        Err(error) => {
            terminate(&mut child);
            return Err(error.to_string().into());
        }
    };
    if state.stopping.load(Ordering::SeqCst) {
        terminate(&mut child);
        return Err("Startup cancelled".into());
    }
    *slot = Some(child);
    Ok(())
}

fn terminate(child: &mut Child) {
    match child.try_wait() {
        Ok(Some(_)) => return,
        Ok(None) => {}
        Err(error) => eprintln!("Could not inspect backend: {error}"),
    }
    if let Err(error) = child.kill() {
        eprintln!("Could not stop backend: {error}");
    }
    if let Err(error) = child.wait() {
        eprintln!("Could not reap backend: {error}");
    }
}

pub fn stop(app: &tauri::AppHandle) {
    let state = app.state::<Backend>();
    match state.child.lock() {
        Ok(mut slot) => {
            if let Some(mut child) = slot.take() {
                terminate(&mut child);
            }
        }
        Err(error) => eprintln!("Could not access backend process: {error}"),
    };
}
