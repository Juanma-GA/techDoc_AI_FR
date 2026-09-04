// Selects the right adapters for the current runtime.
import type { FileSystemPort } from "../ports/FileSystemPort";
import type { StoragePort } from "../ports/StoragePort";
import type { ResourcePort } from "../ports/ResourcePort";
import { BrowserFileSystem } from "./browser/BrowserFileSystem";
import { BrowserStorage } from "./browser/BrowserStorage";
import { BrowserResource } from "./browser/BrowserResource";
import { TauriFileSystem, isTauri } from "./tauri/TauriFileSystem";
import { TauriStorage } from "./tauri/TauriStorage";
import { TauriResource } from "./tauri/TauriResource";

export function createFileSystem(): FileSystemPort {
  return isTauri() ? new TauriFileSystem() : new BrowserFileSystem();
}

export function createStorage(): StoragePort {
  return isTauri() ? new TauriStorage() : new BrowserStorage();
}

export function createResource(): ResourcePort {
  return isTauri() ? new TauriResource() : new BrowserResource();
}
