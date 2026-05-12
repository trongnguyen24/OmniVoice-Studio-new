//! Local OmniVoice Server — Tauri desktop shell.

pub mod backend;
pub mod bootstrap;
pub mod commands;
pub mod config;
pub mod tools;

use std::process::Child;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use tauri::menu::{MenuBuilder, MenuItemBuilder};
use tauri::tray::TrayIconBuilder;
use tauri::Manager;

use crate::bootstrap::{set_stage, BootstrapStage, BootstrapState};

pub fn backend_port() -> u16 {
    std::env::var("OMNIVOICE_PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(3900)
}

pub struct BackendState {
    pub process: Mutex<Option<Child>>,
}

pub struct AppFlags {
    pub quitting: AtomicBool,
}

pub struct TrayHandle {
    pub tray: Mutex<Option<tauri::tray::TrayIcon>>,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            log::info!("Second instance attempted — focusing dashboard");
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.show();
                let _ = win.unminimize();
                let _ = win.set_focus();
            }
        }))
        .invoke_handler(tauri::generate_handler![
            bootstrap::bootstrap_status,
            bootstrap::get_bootstrap_logs,
            bootstrap::retry_bootstrap,
            bootstrap::clean_and_retry_bootstrap,
            config::get_region,
            config::set_region,
            commands::get_sysinfo,
            commands::read_log_tail,
            commands::hf_cache_scan,
            commands::quit_app,
        ])
        .setup(|app| {
            app.handle().plugin(tauri_plugin_dialog::init())?;
            app.handle().plugin(tauri_plugin_updater::Builder::new().build())?;
            app.handle().plugin(tauri_plugin_process::init())?;
            app.handle().plugin(tauri_plugin_opener::init())?;
            app.handle()
                .plugin(tauri_plugin_window_state::Builder::default().build())?;
            app.handle().plugin(
                tauri_plugin_log::Builder::new()
                    .level(log::LevelFilter::Info)
                    .targets([
                        tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::LogDir {
                            file_name: Some("tauri".into()),
                        }),
                        tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::Stdout),
                    ])
                    .build(),
            )?;

            app.manage(AppFlags {
                quitting: AtomicBool::new(false),
            });
            app.manage(TrayHandle {
                tray: Mutex::new(None),
            });

            let show_i = MenuItemBuilder::new("Show Server Dashboard")
                .id("show")
                .build(app)?;
            let quit_i = MenuItemBuilder::new("Quit TTS Server")
                .id("quit")
                .build(app)?;
            let tray_menu = MenuBuilder::new(app)
                .item(&show_i)
                .separator()
                .item(&quit_i)
                .build()?;

            let tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&tray_menu)
                .tooltip("Local OmniVoice Server")
                .on_menu_event(|app, event| match event.id().as_ref() {
                    "show" => {
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.show();
                            #[cfg(not(target_os = "macos"))]
                            let _ = win.set_skip_taskbar(false);
                            let _ = win.set_focus();
                        }
                    }
                    "quit" => {
                        app.state::<AppFlags>()
                            .quitting
                            .store(true, Ordering::SeqCst);
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;
            if let Ok(mut slot) = app.state::<TrayHandle>().tray.lock() {
                *slot = Some(tray);
            }

            #[cfg(target_os = "linux")]
            {
                if let Some(win) = app.get_webview_window("main") {
                    let _ = win.with_webview(|webview| {
                        use webkit2gtk::{PermissionRequestExt, SettingsExt, WebViewExt};
                        let wk = webview.inner();
                        if let Some(settings) = WebViewExt::settings(&wk) {
                            settings.set_media_playback_requires_user_gesture(false);
                        }
                        wk.connect_permission_request(|_, request| {
                            request.allow();
                            true
                        });
                    });
                }
            }

            let bootstrap_state = BootstrapState {
                stage: Arc::new(Mutex::new(BootstrapStage::Checking)),
                logs: Arc::new(Mutex::new(Vec::new())),
            };
            let stage_handle = bootstrap_state.stage.clone();
            app.manage(bootstrap_state);
            app.manage(BackendState {
                process: Mutex::new(None),
            });

            let app_handle = app.handle().clone();
            std::thread::spawn(move || {
                let skip_spawn = std::env::var("TAURI_SKIP_BACKEND").is_ok();
                if skip_spawn {
                    log::info!("TAURI_SKIP_BACKEND set — not spawning");
                    set_stage(&stage_handle, BootstrapStage::Ready);
                    return;
                }
                if backend::backend_healthy(backend_port()) {
                    log::info!("Port {} already serving local backend — attaching", backend_port());
                    set_stage(&stage_handle, BootstrapStage::Ready);
                    return;
                }
                if backend::port_in_use(backend_port()) {
                    log::warn!("Port {} in use — taking ownership", backend_port());
                    backend::kill_orphan_on_port(backend_port());
                    std::thread::sleep(Duration::from_millis(500));
                }

                let child = backend::spawn_backend(&app_handle, Some(&stage_handle));
                if let Ok(mut guard) = app_handle.state::<BackendState>().process.lock() {
                    *guard = child;
                }

                let start = std::time::Instant::now();
                while start.elapsed() < Duration::from_secs(300) {
                    if backend::backend_healthy(backend_port()) {
                        set_stage(&stage_handle, BootstrapStage::Ready);
                        return;
                    }
                    let process_dead = if let Ok(mut guard) = app_handle.state::<BackendState>().process.lock() {
                        match guard.as_mut() {
                            Some(child) => match child.try_wait() {
                                Ok(Some(status)) => Some(status.to_string()),
                                Ok(None) => None,
                                Err(_) => Some("unknown".to_string()),
                            },
                            None => Some("never started".to_string()),
                        }
                    } else {
                        None
                    };
                    if let Some(exit_info) = process_dead {
                        let err_tail = backend::read_error_log_tail(30);
                        let msg = if err_tail.is_empty() {
                            format!("Backend process exited ({exit_info}) — no error output captured")
                        } else {
                            format!("Backend process exited ({exit_info}):\n{err_tail}")
                        };
                        log::error!("Backend died early: {msg}");
                        set_stage(&stage_handle, BootstrapStage::Failed { message: msg });
                        return;
                    }
                    std::thread::sleep(Duration::from_millis(500));
                }

                let err_tail = backend::read_error_log_tail(20);
                let msg = if err_tail.is_empty() {
                    "Backend did not respond within 300 s".to_string()
                } else {
                    format!("Backend did not respond within 300 s. Last stderr output:\n{err_tail}")
                };
                set_stage(&stage_handle, BootstrapStage::Failed { message: msg });
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if window.label() != "main" {
                    return;
                }
                let quitting = window
                    .app_handle()
                    .state::<AppFlags>()
                    .quitting
                    .load(Ordering::SeqCst);
                if quitting {
                    return;
                }
                api.prevent_close();
                let _ = window.hide();
                #[cfg(not(target_os = "macos"))]
                {
                    let _ = window.set_skip_taskbar(true);
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::ExitRequested { .. } = event {
            if let Ok(mut lock) = app_handle.state::<BackendState>().process.lock() {
                if let Some(ref mut child) = *lock {
                    let pid = child.id();
                    log::info!("Shutting down backend (pid {pid})");

                    #[cfg(unix)]
                    {
                        unsafe {
                            libc::kill(pid as i32, libc::SIGTERM);
                        }
                        let start = std::time::Instant::now();
                        loop {
                            match child.try_wait() {
                                Ok(Some(_)) => break,
                                Ok(None) if start.elapsed() < Duration::from_secs(2) => {
                                    std::thread::sleep(Duration::from_millis(100));
                                }
                                _ => {
                                    log::warn!("Backend didn't exit in 2 s — SIGKILL");
                                    let _ = child.kill();
                                    break;
                                }
                            }
                        }
                    }
                    #[cfg(not(unix))]
                    {
                        let _ = child.kill();
                    }
                    let _ = child.wait();
                }
            }
        }
    });
}
