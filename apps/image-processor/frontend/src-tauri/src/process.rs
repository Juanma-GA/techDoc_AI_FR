use std::{
    error::Error,
    process::Child,
    sync::{
        atomic::{AtomicBool, Ordering},
        Mutex,
    },
    thread,
    time::{Duration, Instant},
};

type Result<T> = std::result::Result<T, Box<dyn Error>>;

pub fn register(
    mut child: Child,
    slot: &Mutex<Option<Child>>,
    stopping: &AtomicBool,
) -> Result<()> {
    let mut slot = match slot.lock() {
        Ok(slot) => slot,
        Err(error) => {
            terminate(&mut child);
            return Err(error.to_string().into());
        }
    };
    if stopping.load(Ordering::SeqCst) {
        terminate(&mut child);
        return Err("Startup cancelled".into());
    }
    if slot.is_some() {
        terminate(&mut child);
        return Err("Service process is already registered".into());
    }
    *slot = Some(child);
    Ok(())
}

pub fn ensure_running(slot: &Mutex<Option<Child>>, name: &str) -> Result<()> {
    let mut slot = slot.lock().map_err(|error| error.to_string())?;
    let Some(child) = slot.as_mut() else {
        return Err(format!("{name} process is not running").into());
    };
    if let Some(status) = child.try_wait()? {
        *slot = None;
        return Err(format!("{name} process exited: {status}").into());
    }
    Ok(())
}

pub fn wait_for_success(
    mut child: Child,
    stopping: &AtomicBool,
    timeout: Duration,
    name: &str,
) -> Result<()> {
    let deadline = Instant::now() + timeout;
    loop {
        if stopping.load(Ordering::SeqCst) {
            terminate(&mut child);
            return Err("Startup cancelled".into());
        }
        match child.try_wait() {
            Ok(Some(status)) if status.success() => return Ok(()),
            Ok(Some(status)) => return Err(format!("{name} failed: {status}").into()),
            Ok(None) => {}
            Err(error) => {
                terminate(&mut child);
                return Err(error.into());
            }
        }
        if Instant::now() >= deadline {
            terminate(&mut child);
            return Err(format!("{name} timed out").into());
        }
        thread::sleep(Duration::from_millis(100));
    }
}

pub fn terminate(child: &mut Child) {
    match child.try_wait() {
        Ok(Some(_)) => return,
        Ok(None) => {}
        Err(error) => eprintln!("Could not inspect child process: {error}"),
    }
    if let Err(error) = child.kill() {
        eprintln!("Could not stop child process: {error}");
    }
    if let Err(error) = child.wait() {
        eprintln!("Could not reap child process: {error}");
    }
}

pub fn stop(slot: &Mutex<Option<Child>>, name: &str) {
    match slot.lock() {
        Ok(mut slot) => {
            if let Some(mut child) = slot.take() {
                terminate(&mut child);
            }
        }
        Err(error) => eprintln!("Could not access {name} process: {error}"),
    }
}
