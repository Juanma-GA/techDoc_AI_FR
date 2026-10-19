use crate::{
    health::healthy,
    process::{self, ensure_running, register, wait_for_success},
    spec::{ModelCache, Service, Spec},
};
use std::{
    error::Error,
    net::{SocketAddr, TcpListener},
    path::{Path, PathBuf},
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
const MODEL_STARTUP_TIMEOUT: Duration = Duration::from_secs(600);

#[derive(Default)]
pub struct Backend {
    api: Mutex<Option<Child>>,
    lama: Mutex<Option<Child>>,
    pub stopping: AtomicBool,
}

pub fn start(app: &tauri::AppHandle, window: &WebviewWindow) -> Result<()> {
    let spec: Spec = serde_json::from_str(include_str!("../runtime.json"))?;
    let state = app.state::<Backend>();
    let root = if spec.root.is_empty() {
        app.path().resource_dir()?
    } else {
        PathBuf::from(&spec.root)
    };
    let data = app.path().app_local_data_dir()?;
    let storage = data.join("storage");
    std::fs::create_dir_all(&storage)?;
    let database = format!(
        "sqlite:///{}",
        data.join(format!("{}.db", spec.slug)).display()
    )
    .replace('\\', "/");
    let (api_address, lama_address) = free_addresses()?;

    let mut bootstrap = api_command(
        &root,
        &spec.api,
        &spec.bootstrap,
        api_address.port(),
        lama_address.port(),
        &database,
        &storage,
        spec.model_cache.as_ref(),
    );
    let child = bootstrap.spawn()?;
    wait_for_success(
        child,
        &state.stopping,
        Duration::from_secs(60),
        "Database migration",
    )?;

    let mut lama = lama_command(
        &root,
        &spec.lama,
        lama_address.port(),
        spec.model_cache.as_ref(),
    );
    let child = lama.spawn()?;
    register(child, &state.lama, &state.stopping)?;
    wait_for_service(
        app,
        &spec.lama,
        lama_address,
        &state.lama,
        MODEL_STARTUP_TIMEOUT,
    )?;

    let mut api = api_command(
        &root,
        &spec.api,
        &spec.api.args,
        api_address.port(),
        lama_address.port(),
        &database,
        &storage,
        spec.model_cache.as_ref(),
    );
    let child = api.spawn()?;
    register(child, &state.api, &state.stopping)?;
    wait_for_service(
        app,
        &spec.api,
        api_address,
        &state.api,
        MODEL_STARTUP_TIMEOUT,
    )?;
    window.navigate(format!("http://{api_address}/").parse()?)?;
    Ok(())
}

fn free_addresses() -> Result<(SocketAddr, SocketAddr)> {
    let lama = TcpListener::bind("127.0.0.1:0")?;
    let lama_address = lama.local_addr()?;
    let api = TcpListener::bind("127.0.0.1:0")?;
    let api_address = api.local_addr()?;
    drop((lama, api));
    Ok((api_address, lama_address))
}

fn base_command(root: &Path, service: &Service, args: &[String], port: u16) -> Command {
    let mut command = Command::new(root.join(&service.executable));
    command
        .current_dir(root.join(&service.cwd))
        .args(
            args.iter()
                .map(|arg| arg.replace("{port}", &port.to_string())),
        )
        .stdin(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    command
}

fn api_command(
    root: &Path,
    service: &Service,
    args: &[String],
    api_port: u16,
    lama_port: u16,
    database: &str,
    storage: &Path,
    model_cache: Option<&ModelCache>,
) -> Command {
    let mut command = base_command(root, service, args, api_port);
    command
        .env("DATABASE_URL", database)
        .env("STORAGE_DIR", storage)
        .env("BIND_HOST", "127.0.0.1")
        .env("LAMA_SERVICE_PORT", lama_port.to_string())
        .env("DESKTOP_PRELOAD_MODELS", "true");
    if let Some(cache) = model_cache {
        command
            .env("OCR_MODEL_VARIANT", &cache.ocr_model_variant)
            .env("PADDLE_PDX_CACHE_HOME", root.join(&cache.paddlex));
    }
    command
}

fn lama_command(
    root: &Path,
    service: &Service,
    port: u16,
    model_cache: Option<&ModelCache>,
) -> Command {
    let mut command = base_command(root, service, &service.args, port);
    command.env("DESKTOP_PRELOAD_MODELS", "true");
    if let Some(cache) = model_cache {
        command
            .env("TORCH_HOME", root.join(&cache.torch_home))
            .env("LAMA_MODEL_URL", &cache.lama_model_url);
    }
    command
}

fn wait_for_service(
    app: &tauri::AppHandle,
    service: &Service,
    address: SocketAddr,
    child: &Mutex<Option<Child>>,
    timeout: Duration,
) -> Result<()> {
    let state = app.state::<Backend>();
    let deadline = Instant::now() + timeout;
    loop {
        if state.stopping.load(Ordering::SeqCst) {
            return Err("Startup cancelled".into());
        }
        ensure_running(child, &service.health_path)?;
        if healthy(address, &service.health_path) {
            return Ok(());
        }
        if Instant::now() >= deadline {
            return Err(format!("{} health check timed out", service.health_path).into());
        }
        thread::sleep(Duration::from_millis(100));
    }
}

pub fn stop(app: &tauri::AppHandle) {
    let state = app.state::<Backend>();
    process::stop(&state.api, "API");
    process::stop(&state.lama, "LaMa");
}
