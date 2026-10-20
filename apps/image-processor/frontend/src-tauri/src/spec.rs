use serde::Deserialize;

#[derive(Deserialize)]
pub struct Service {
    pub executable: String,
    pub cwd: String,
    pub args: Vec<String>,
    pub health_path: String,
}

#[derive(Deserialize)]
pub struct ModelCache {
    pub paddlex: String,
    pub torch_home: String,
    pub ocr_model_variant: String,
    pub lama_model_url: String,
}

#[derive(Deserialize)]
pub struct Spec {
    pub root: String,
    pub slug: String,
    pub api: Service,
    pub lama: Service,
    pub bootstrap: Vec<String>,
    pub model_cache: Option<ModelCache>,
}
