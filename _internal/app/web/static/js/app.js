document.addEventListener("DOMContentLoaded", function () {
  // =============== COMMON ELEMENTS ===============
  // Index page elements
  const authStatus = document.getElementById("auth-status");
  const loginBtn = document.getElementById("login-btn");
  const logoutBtn = document.getElementById("logout-btn");
  const authInstructions = document.getElementById("auth-instructions");
  const verificationUrl = document.getElementById("verification-url");
  const verificationCode = document.getElementById("verification-code");
  const refreshDownloadsBtn = document.getElementById("refresh-downloads-btn");
  const downloadsBody = document.getElementById("downloads-body");
  const addDownloadForm = document.getElementById("add-download-form");
  const seriesIdSelect = document.getElementById("series-id");
  const watcherStatus = document.getElementById("watcher-status");
  const startWatcherForm = document.getElementById("start-watcher-form");

  // Dashboard/Torrents page elements
  const autoRefreshCheckbox = document.getElementById("auto-refresh");
  const refreshButton = document.getElementById("refresh-btn");
  const torrentsTableBody = document.getElementById("torrents-table-body");

  // =============== INITIALIZATION ===============
  // Initialize based on page content

  // Initialize progress bars
  initializeProgressBars();

  // Index page initialization
  if (authStatus) {
    checkAuthStatus();
    if (seriesIdSelect) loadSeries();
    if (downloadsBody) getDownloads();
    if (watcherStatus) checkWatcherStatus();
  }

  // Auth polling initialization
  if (
    document.querySelector(".auth-polling-page") ||
    document.getElementById("auth-progress")
  ) {
    initAuthPollingPage();
  }

  // Reauth page initialization
  if (document.getElementById("auto-check")) {
    document
      .getElementById("auto-check")
      .addEventListener("change", startAutoCheck);
  }

  // Initialize the reauth page functionality
  if (document.getElementById("start-auth")) {
    initReauthPage();
  }

  // Dashboard/Torrents page initialization
  if (autoRefreshCheckbox) {
    let refreshInterval;
    autoRefreshCheckbox.addEventListener("change", function () {
      if (this.checked) {
        refreshInterval = setInterval(fetchTorrentData, 10000); // Refresh every 10 seconds
      } else {
        clearInterval(refreshInterval);
      }
    });
  }

  if (refreshButton) {
    refreshButton.addEventListener("click", fetchTorrentData);
  }

  // File browser initialization
  if (document.getElementById("select-folder")) {
    document.getElementById("select-folder").addEventListener("click", () => {
      document.getElementById(currentTarget).value = currentPath;
      closeFolderBrowser();
    });
  }

  // =============== EVENT LISTENERS ===============
  // Only add event listeners if elements exist
  if (loginBtn) loginBtn.addEventListener("click", login);
  if (logoutBtn) logoutBtn.addEventListener("click", logout);
  if (refreshDownloadsBtn)
    refreshDownloadsBtn.addEventListener("click", getDownloads);

  if (addDownloadForm) {
    addDownloadForm.addEventListener("submit", function (e) {
      e.preventDefault();
      addDownload();
    });
  }

  if (startWatcherForm) {
    startWatcherForm.addEventListener("submit", function (e) {
      e.preventDefault();
      startWatcher();
    });
  }

  // =============== AUTHENTICATION FUNCTIONS ===============
  function checkAuthStatus() {
    fetch("/api/auth/status")
      .then((response) => response.json())
      .then((data) => {
        if (data.authenticated) {
          authStatus.textContent = "Authenticated with Seedr";
          authStatus.classList.add("text-success");
          loginBtn.style.display = "none";
          logoutBtn.style.display = "inline-block";
          authInstructions.style.display = "none";
        } else {
          authStatus.textContent = "Not authenticated with Seedr";
          authStatus.classList.add("text-danger");
          loginBtn.style.display = "inline-block";
          logoutBtn.style.display = "none";
        }
      })
      .catch((error) => {
        console.error("Error checking auth status:", error);
        authStatus.textContent = "Error checking authentication status";
        authStatus.classList.add("text-danger");
      });
  }

  function login() {
    fetch("/api/auth/login", {
      method: "POST",
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          authInstructions.style.display = "block";
          verificationUrl.textContent = data.verification_uri;
          verificationUrl.href = data.verification_uri;
          verificationCode.textContent = data.user_code;

          // Check auth status every 5 seconds
          const interval = setInterval(() => {
            fetch("/api/auth/status")
              .then((response) => response.json())
              .then((statusData) => {
                if (statusData.authenticated) {
                  clearInterval(interval);
                  checkAuthStatus();
                }
              });
          }, 5000);
        } else {
          alert("Error initiating login");
        }
      })
      .catch((error) => {
        console.error("Error logging in:", error);
        alert("Error initiating login");
      });
  }

  function logout() {
    fetch("/api/auth/logout", {
      method: "POST",
    })
      .then(() => {
        checkAuthStatus();
      })
      .catch((error) => {
        console.error("Error logging out:", error);
        alert("Error logging out");
      });
  }

  // Function for the reauth.html page
  function initReauthPage() {
    const startAuthBtn = document.getElementById("start-auth");
    const authStatus = document
      .getElementById("auth-status")
      .querySelector("p");

    startAuthBtn.addEventListener("click", function () {
      // Disable button
      startAuthBtn.disabled = true;
      authStatus.textContent = "Starting authentication process...";

      // Start authentication process
      fetch("/api/auth/login", {
        method: "POST",
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.success) {
            // Redirect to polling page
            window.location.href = `/auth-polling?user_code=${encodeURIComponent(
              data.user_code
            )}&verification_uri=${encodeURIComponent(data.verification_uri)}`;
          } else {
            authStatus.textContent =
              "Error starting authentication. Please try again.";
            startAuthBtn.disabled = false;
          }
        })
        .catch((error) => {
          console.error("Error starting authentication:", error);
          authStatus.textContent =
            "Error starting authentication. Please try again.";
          startAuthBtn.disabled = false;
        });
    });
  }

  // Function for auth_polling.html
  function initAuthPollingPage() {
    // Get values from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const userCode = urlParams.get("user_code");
    const verificationUri = urlParams.get("verification_uri");

    if (!userCode || !verificationUri) {
      console.error("Missing required parameters for auth polling");
      return;
    }

    // Full URL including user code
    const authUrl = `${verificationUri}?code=${userCode}`;

    // Log the URL for debugging (can be removed in production)
    console.log("Authentication URL:", authUrl);

    // Attempt to open the authentication page in a new tab
    try {
      const newTab = window.open(authUrl, "_blank");
      if (!newTab || newTab.closed || typeof newTab.closed == "undefined") {
        console.log(
          "Popup blocked or failed to open. User will need to click the button manually."
        );
      }
    } catch (e) {
      console.error("Error opening authentication window:", e);
    }

    let pollCount = 0;
    const maxPolls = 60; // 5 minutes (polling every 5 seconds)
    const statusElement = document.querySelector(".auth-status p");
    const progressBar = document.getElementById("auth-progress");

    if (!statusElement || !progressBar) {
      console.error("Missing required elements for auth polling page");
      return;
    }

    // Start polling
    let pollInterval = setInterval(pollAuthStatus, 5000);

    // Also poll immediately
    setTimeout(pollAuthStatus, 500);

    function updateProgress(count) {
      const progress = Math.min(Math.floor((count / maxPolls) * 100), 99);
      progressBar.style.width = progress + "%";
      progressBar.textContent = progress + "%";
      progressBar.setAttribute("data-progress", progress);
    }

    function pollAuthStatus() {
      pollCount++;
      updateProgress(pollCount);

      fetch("/api/auth/poll")
        .then((response) => response.json())
        .then((data) => {
          if (data.success) {
            // Authentication successful
            clearInterval(pollInterval);
            statusElement.textContent =
              "Authentication successful! Redirecting...";
            progressBar.style.width = "100%";
            progressBar.textContent = "100%";
            progressBar.setAttribute("data-progress", 100);

            // Redirect to config or dashboard
            setTimeout(() => {
              window.location.href = data.redirect || "/config";
            }, 1500);
          } else if (pollCount < maxPolls) {
            // Continue polling
          } else {
            // Timeout
            clearInterval(pollInterval);
            statusElement.textContent =
              "Authentication timed out. Please try again.";
            const authContainer = document.querySelector(".auth-container");
            authContainer.innerHTML +=
              '<div class="auth-actions"><a href="/reauth" class="button">Try Again</a></div>';
          }
        })
        .catch((error) => {
          console.error("Error polling auth status:", error);
          statusElement.textContent = "Error checking authentication status.";
        });
    }
  }

  // Auth polling related functions (older version, kept for compatibility)
  function startPolling() {
    const pollInterval = setInterval(checkAuthPollStatus, 5000);
    // Also check immediately
    checkAuthPollStatus();

    // Open the verification URL in a new tab if it exists
    const verificationUrlElement = document.getElementById(
      "verification-url-link"
    );
    if (verificationUrlElement && verificationUrlElement.href) {
      window.open(verificationUrlElement.href, "_blank");
    }
  }

  function checkAuthPollStatus() {
    fetch("/api/auth/poll")
      .then((response) => response.json())
      .then((data) => {
        const statusElement = document.getElementById("status");
        if (!statusElement) return;

        if (data.success) {
          clearInterval(pollInterval);
          statusElement.innerHTML =
            '<div class="alert alert-success">Authentication successful! Redirecting...</div>';
          setTimeout(() => {
            window.location.href = data.redirect || "/";
          }, 2000);
        } else {
          statusElement.innerHTML =
            '<div class="alert alert-info">Waiting for authentication...</div>';
        }
      })
      .catch((error) => {
        const statusElement = document.getElementById("status");
        if (statusElement) {
          statusElement.innerHTML =
            '<div class="alert alert-danger">Error checking status: ' +
            error +
            "</div>";
        }
      });
  }

  // Functions for reauth.html
  function startAutoCheck() {
    const checkbox = document.getElementById("auto-check");
    if (!checkbox) return;

    if (checkbox.checked) {
      // Check every 5 seconds
      checkTimer = setInterval(checkAuthStatusReauth, 5000);
      console.log("Auto-check enabled");
    } else {
      if (checkTimer) {
        clearInterval(checkTimer);
        checkTimer = null;
        console.log("Auto-check disabled");
      }
    }
  }

  function checkAuthStatusReauth() {
    fetch("/api/auth/status")
      .then((response) => response.json())
      .then((data) => {
        if (data.authenticated) {
          console.log("Authentication found, redirecting...");
          window.location.href = data.redirect;
        } else {
          console.log("Not authenticated yet");
        }
      })
      .catch((error) => {
        console.error("Error checking auth status:", error);
      });
  }

  // =============== DOWNLOADS FUNCTIONS ===============
  function loadSeries() {
    fetch("/api/sonarr/series")
      .then((response) => response.json())
      .then((data) => {
        // Clear options
        seriesIdSelect.innerHTML = '<option value="">None</option>';

        // Add options
        data.forEach((series) => {
          const option = document.createElement("option");
          option.value = series.id;
          option.textContent = series.title;
          seriesIdSelect.appendChild(option);
        });
      })
      .catch((error) => {
        console.error("Error loading series:", error);
      });
  }

  function getDownloads() {
    fetch("/api/downloads")
      .then((response) => response.json())
      .then((data) => {
        // Clear table
        downloadsBody.innerHTML = "";

        if (data.length === 0) {
          const row = document.createElement("tr");
          row.innerHTML = '<td colspan="4">No downloads found</td>';
          downloadsBody.appendChild(row);
          return;
        }

        // Add rows
        data.forEach((download) => {
          const row = document.createElement("tr");

          // Title
          const titleCell = document.createElement("td");
          titleCell.textContent = download.title;
          titleCell.classList.add("title-col");
          row.appendChild(titleCell);

          // Status
          const statusCell = document.createElement("td");
          statusCell.textContent = download.status;
          row.appendChild(statusCell);

          // Progress
          const progressCell = document.createElement("td");
          const progress = download.progress || 0;
          progressCell.innerHTML = `
                <div class="progress">
                    <div class="progress-bar" role="progressbar" style="width: ${progress}%;" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100">${progress}%</div>
                </div>
            `;
          row.appendChild(progressCell);

          // Actions
          const actionsCell = document.createElement("td");
          actionsCell.innerHTML = `
                <div class="btn-group-sm">
                    <button class="btn btn-sm btn-info action-btn" data-action="files" data-title="${
                      download.title
                    }">Files</button>
                    <button class="btn btn-sm btn-success action-btn" data-action="download" data-title="${
                      download.title
                    }">Download</button>
                    <button class="btn btn-sm btn-warning action-btn" data-action="notify" data-title="${
                      download.title
                    }">Notify Sonarr</button>
                    ${
                      download.status === "downloading"
                        ? `<button class="btn btn-sm btn-secondary action-btn" data-action="pause" data-title="${download.title}">Pause</button>`
                        : ""
                    }
                    ${
                      download.status === "paused"
                        ? `<button class="btn btn-sm btn-primary action-btn" data-action="resume" data-title="${download.title}">Resume</button>`
                        : ""
                    }
                    <button class="btn btn-sm btn-danger action-btn" data-action="delete" data-title="${
                      download.title
                    }">Delete</button>
                </div>
            `;
          row.appendChild(actionsCell);

          downloadsBody.appendChild(row);
        });

        // Add event listeners to buttons
        document.querySelectorAll(".action-btn").forEach((button) => {
          button.addEventListener("click", handleAction);
        });
      })
      .catch((error) => {
        console.error("Error getting downloads:", error);
        downloadsBody.innerHTML =
          '<tr><td colspan="4">Error loading downloads</td></tr>';
      });
  }

  function handleAction(e) {
    const action = e.target.dataset.action;
    const title = e.target.dataset.title;

    switch (action) {
      case "files":
        window.open(
          `/api/downloads/${encodeURIComponent(title)}/files`,
          "_blank"
        );
        break;
      case "download":
        downloadFiles(title);
        break;
      case "notify":
        notifySonarr(title);
        break;
      case "pause":
        pauseTorrent(title);
        break;
      case "resume":
        resumeTorrent(title);
        break;
      case "delete":
        deleteTorrent(title);
        break;
    }
  }

  function addDownload() {
    const title = document.getElementById("title").value;
    const downloadUrl = document.getElementById("download-url").value;
    const seriesId = document.getElementById("series-id").value;

    fetch("/api/downloads", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title: title,
        download_url: downloadUrl,
        series_id: seriesId ? parseInt(seriesId) : null,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          alert(`Added download: ${data.message}`);
          document.getElementById("title").value = "";
          document.getElementById("download-url").value = "";
          document.getElementById("series-id").value = "";
          getDownloads();
        } else {
          alert(`Error: ${data.message}`);
        }
      })
      .catch((error) => {
        console.error("Error adding download:", error);
        alert("Error adding download");
      });
  }

  // Dashboard and torrents page functions
  function fetchTorrentData() {
    fetch("/api/downloads")
      .then((response) => response.json())
      .then((data) => {
        updateTorrentTable(data);
        updateProgressBars(); // Initialize progress bars after updating the table
      })
      .catch((error) => {
        console.error("Error fetching torrents:", error);
      });
  }

  function updateTorrentTable(torrents) {
    const tableBody = torrentsTableBody;
    if (!tableBody) return;

    tableBody.innerHTML = "";

    if (torrents.length === 0) {
      const emptyRow = document.createElement("tr");
      emptyRow.innerHTML =
        '<td colspan="5" class="empty-state">No active torrents found</td>';
      tableBody.appendChild(emptyRow);
      return;
    }

    torrents.forEach((torrent) => {
      const row = document.createElement("tr");

      // Create torrent name cell
      const nameCell = document.createElement("td");
      nameCell.textContent = torrent.title;
      row.appendChild(nameCell);

      // Create status cell
      const statusCell = document.createElement("td");
      let statusClass = "";
      if (torrent.status === "completed") {
        statusClass = "status-completed";
      } else if (torrent.status === "downloading") {
        statusClass = "status-downloading";
      } else if (torrent.status === "error") {
        statusClass = "status-error";
      }
      statusCell.innerHTML = `<span class="${statusClass}">${torrent.status}</span>`;
      row.appendChild(statusCell);

      // Create progress cell
      const progressCell = document.createElement("td");
      const progressPercent = torrent.progress || 0;
      progressCell.innerHTML = `
          <div class="progress-bar">
              <div class="progress-fill" data-progress="${progressPercent}">${progressPercent}%</div>
          </div>
      `;
      row.appendChild(progressCell);

      // Create size cell
      const sizeCell = document.createElement("td");
      sizeCell.textContent = torrent.size || "Unknown";
      row.appendChild(sizeCell);

      // Create actions cell
      const actionsCell = document.createElement("td");
      actionsCell.className = "actions";

      // Add action buttons based on torrent status
      if (torrent.status === "completed") {
        actionsCell.innerHTML = `
          <button class="action-btn" onclick="downloadFiles('${torrent.title}')">Download</button>
          <button class="action-btn" onclick="notifySonarr('${torrent.title}')">Notify Sonarr</button>
          <button class="action-btn" onclick="deleteTorrent('${torrent.title}')">Delete</button>
        `;
      } else if (torrent.status === "downloading") {
        actionsCell.innerHTML = `
          <button class="action-btn" onclick="pauseTorrent('${torrent.title}')">Pause</button>
          <button class="action-btn" onclick="deleteTorrent('${torrent.title}')">Delete</button>
        `;
      } else {
        actionsCell.innerHTML = `
          <button class="action-btn" onclick="deleteTorrent('${torrent.title}')">Delete</button>
        `;
      }

      row.appendChild(actionsCell);
      tableBody.appendChild(row);
    });
  }

  // Common torrent action functions
  function downloadFiles(title) {
    fetch(`/api/downloads/${encodeURIComponent(title)}/download`, {
      method: "POST",
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to start download");
        }
        return response.json();
      })
      .then((data) => {
        alert("Download started successfully");
        // Refresh the table
        if (document.getElementById("refresh-btn")) {
          document.getElementById("refresh-btn").click();
        } else {
          getDownloads();
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        alert("Error starting download: " + error.message);
      });
  }

  function notifySonarr(title) {
    fetch(`/api/downloads/${encodeURIComponent(title)}/notify-sonarr`, {
      method: "POST",
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to notify Sonarr");
        }
        return response.json();
      })
      .then((data) => {
        alert("Sonarr notified successfully");
        // Refresh the table
        if (document.getElementById("refresh-btn")) {
          document.getElementById("refresh-btn").click();
        } else {
          getDownloads();
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        alert("Error notifying Sonarr: " + error.message);
      });
  }

  function pauseTorrent(title) {
    fetch(`/api/downloads/${encodeURIComponent(title)}/pause`, {
      method: "POST",
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to pause torrent");
        }
        return response.json();
      })
      .then((data) => {
        alert("Torrent paused successfully");
        // Refresh the table
        if (document.getElementById("refresh-btn")) {
          document.getElementById("refresh-btn").click();
        } else {
          getDownloads();
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        alert("Error pausing torrent: " + error.message);
      });
  }

  function resumeTorrent(title) {
    fetch(`/api/downloads/${encodeURIComponent(title)}/resume`, {
      method: "POST",
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to resume torrent");
        }
        return response.json();
      })
      .then((data) => {
        alert("Torrent resumed successfully");
        // Refresh the table
        if (document.getElementById("refresh-btn")) {
          document.getElementById("refresh-btn").click();
        } else {
          getDownloads();
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        alert("Error resuming torrent: " + error.message);
      });
  }

  function deleteTorrent(title) {
    if (confirm("Are you sure you want to delete this torrent?")) {
      fetch(`/api/downloads/${encodeURIComponent(title)}`, {
        method: "DELETE",
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error("Failed to delete torrent");
          }
          return response.json();
        })
        .then((data) => {
          alert("Torrent deleted successfully");
          // Refresh the table
          if (document.getElementById("refresh-btn")) {
            document.getElementById("refresh-btn").click();
          } else {
            getDownloads();
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          alert("Error deleting torrent: " + error.message);
        });
    }
  }

  // =============== WATCHER FUNCTIONS ===============
  function checkWatcherStatus() {
    fetch("/api/watcher/status")
      .then((response) => response.json())
      .then((data) => {
        if (data.running) {
          watcherStatus.textContent = "Watcher is running";
          watcherStatus.classList.add("text-success");
        } else {
          watcherStatus.textContent = "Watcher is not running";
          watcherStatus.classList.add("text-danger");
        }
      })
      .catch((error) => {
        console.error("Error checking watcher status:", error);
        watcherStatus.textContent = "Error checking watcher status";
        watcherStatus.classList.add("text-danger");
      });
  }

  function startWatcher() {
    const torrentDir = document.getElementById("torrent-dir").value;
    const downloadDir = document.getElementById("download-dir").value;

    let url = `/api/watcher/start?torrent_dir=${encodeURIComponent(
      torrentDir
    )}`;
    if (downloadDir) {
      url += `&download_dir=${encodeURIComponent(downloadDir)}`;
    }

    fetch(url, {
      method: "POST",
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          alert(`Started watcher: ${data.message}`);
          checkWatcherStatus();
        } else {
          alert(`Error: ${data.message}`);
        }
      })
      .catch((error) => {
        console.error("Error starting watcher:", error);
        alert("Error starting watcher");
      });
  }

  // =============== FOLDER BROWSER FUNCTIONS ===============
  // Variables for folder browser
  let currentTarget = null;
  let currentPath = "";

  function showTab(tabName) {
    document.querySelectorAll(".tab").forEach((tab) => {
      tab.classList.remove("active");
    });

    const tab = document.querySelector(`[onclick="showTab('${tabName}')"]`);
    if (tab) tab.classList.add("active");

    if (tabName === "settings") {
      document.getElementById("settings-tab").style.display = "block";
      document.getElementById("status-tab").style.display = "none";
    } else {
      document.getElementById("settings-tab").style.display = "none";
      document.getElementById("status-tab").style.display = "block";
      refreshLog(); // Refresh log when showing the status tab
    }
  }

  function browseFolders(targetId) {
    currentTarget = targetId;
    document.getElementById("overlay").style.display = "block";
    document.getElementById("folder-browser").style.display = "block";

    // Use the current value as starting point if it exists
    let initialPath = document.getElementById(targetId).value;
    if (!initialPath) {
      initialPath = "";
    }

    loadFolders(initialPath);
  }

  function closeFolderBrowser() {
    document.getElementById("overlay").style.display = "none";
    document.getElementById("folder-browser").style.display = "none";
  }

  function loadFolders(path) {
    currentPath = path;
    document.getElementById("current-path").textContent =
      path || "Root Directory";

    fetch(`/api/filesystem/folders?path=${encodeURIComponent(path)}`)
      .then((response) => response.json())
      .then((data) => {
        const folderList = document.getElementById("folder-list");
        folderList.innerHTML = "";

        // Add parent directory option if not at root
        if (path) {
          const parentDir = document.createElement("div");
          parentDir.className = "folder-item";
          parentDir.textContent = "..";
          parentDir.addEventListener("click", () => {
            const parentPath = path.split("/").slice(0, -1).join("/");
            loadFolders(parentPath);
          });
          folderList.appendChild(parentDir);
        }

        // Add folders
        if (data.folders && data.folders.length > 0) {
          data.folders.forEach((folder) => {
            const folderItem = document.createElement("div");
            folderItem.className = "folder-item";
            folderItem.textContent = folder;
            folderItem.addEventListener("click", () => {
              const newPath = path ? `${path}/${folder}` : folder;
              loadFolders(newPath);
            });
            folderList.appendChild(folderItem);
          });
        } else {
          const emptyMsg = document.createElement("div");
          emptyMsg.textContent = "No folders found";
          folderList.appendChild(emptyMsg);
        }
      })
      .catch((error) => {
        console.error("Error loading folders:", error);
        const folderList = document.getElementById("folder-list");
        folderList.innerHTML = `<div>Error loading folders: ${error.message}</div>`;
      });
  }

  function refreshLog() {
    fetch("/api/watcher/log")
      .then((response) => response.json())
      .then((data) => {
        const logElement = document.getElementById("activity-log");
        if (logElement) {
          if (data.log && data.log.length > 0) {
            logElement.textContent = data.log.join("\n");
          } else {
            logElement.textContent = "No recent activity";
          }
        }
      })
      .catch((error) => {
        console.error("Error fetching activity log:", error);
      });
  }

  // Make certain functions available globally
  window.downloadFiles = downloadFiles;
  window.notifySonarr = notifySonarr;
  window.pauseTorrent = pauseTorrent;
  window.resumeTorrent = resumeTorrent;
  window.deleteTorrent = deleteTorrent;
  window.browseFolders = browseFolders;
  window.closeFolderBrowser = closeFolderBrowser;
  window.showTab = showTab;
  window.refreshLog = refreshLog;

  // Refresh downloads every 30 seconds
  if (downloadsBody || torrentsTableBody) {
    setInterval(downloadsBody ? getDownloads : fetchTorrentData, 30000);
  }

  // Initialize the dashboard's available torrents and logs sections
  if (document.getElementById("available-torrents-container")) {
    fetchAvailableTorrents();
    document
      .getElementById("refresh-logs-btn")
      ?.addEventListener("click", fetchWatcherLogs);
    document
      .getElementById("log-lines-count")
      ?.addEventListener("change", fetchWatcherLogs);
    fetchWatcherLogs();
  }

  // =============== COMMON FUNCTIONS ===============

  // Set width of progress bars based on data-progress attribute
  function initializeProgressBars() {
    const progressBars = document.querySelectorAll(
      ".progress-fill[data-progress]"
    );
    progressBars.forEach((bar) => {
      const progress = bar.getAttribute("data-progress");
      if (progress) {
        bar.style.width = progress + "%";
      }
    });
  }

  // =============== AVAILABLE TORRENTS FUNCTIONS ===============

  // Fetch available torrents from the watched folder
  function fetchAvailableTorrents() {
    const loadingElement = document.getElementById("torrents-loading");
    const errorElement = document.getElementById("torrents-error");
    const tableElement = document.getElementById("available-torrents-table");
    const noTorrentsElement = document.getElementById("no-torrents-message");

    if (!loadingElement || !errorElement || !tableElement || !noTorrentsElement)
      return;

    // Show loading, hide other elements
    loadingElement.style.display = "block";
    errorElement.style.display = "none";
    tableElement.style.display = "none";
    noTorrentsElement.style.display = "none";

    fetch("/api/watcher/scan")
      .then((response) => response.json())
      .then((data) => {
        loadingElement.style.display = "none";

        if (data.success) {
          if (data.torrents && data.torrents.length > 0) {
            renderTorrentsTable(data.torrents);
            tableElement.style.display = "table";
          } else {
            noTorrentsElement.style.display = "block";
          }
        } else {
          errorElement.textContent =
            data.message || "Failed to scan for torrents";
          errorElement.style.display = "block";
        }
      })
      .catch((error) => {
        loadingElement.style.display = "none";
        errorElement.textContent = `Error: ${error}`;
        errorElement.style.display = "block";
      });
  }

  function renderTorrentsTable(torrents) {
    const tbody = document.getElementById("available-torrents-body");
    if (!tbody) return;

    tbody.innerHTML = "";

    // Sort torrents by modified date (newest first)
    torrents.sort((a, b) => {
      const aTime = a.modified ? new Date(a.modified).getTime() : 0;
      const bTime = b.modified ? new Date(b.modified).getTime() : 0;
      return bTime - aTime;
    });

    torrents.forEach((torrent) => {
      const row = document.createElement("tr");

      // Name cell
      const nameCell = document.createElement("td");
      nameCell.textContent = torrent.name;
      row.appendChild(nameCell);

      // Size cell
      const sizeCell = document.createElement("td");
      sizeCell.textContent = torrent.size || "Unknown";
      row.appendChild(sizeCell);

      // Modified cell
      const modifiedCell = document.createElement("td");
      modifiedCell.textContent = torrent.modified || "Unknown";
      row.appendChild(modifiedCell);

      // Actions cell
      const actionsCell = document.createElement("td");
      actionsCell.className = "actions";

      // Upload button
      const uploadBtn = document.createElement("button");
      uploadBtn.className = "action-btn upload-torrent-btn";
      uploadBtn.textContent = "Upload to Seedr";
      uploadBtn.dataset.path = torrent.path;
      uploadBtn.addEventListener("click", function () {
        uploadTorrent(torrent.path, this);
      });
      actionsCell.appendChild(uploadBtn);

      // Delete button
      const deleteBtn = document.createElement("button");
      deleteBtn.className = "action-btn delete-torrent-btn";
      deleteBtn.textContent = "Delete File";
      deleteBtn.dataset.path = torrent.path;
      deleteBtn.addEventListener("click", function () {
        if (confirm("Are you sure you want to delete this file?")) {
          deleteTorrentFile(torrent.path, this);
        }
      });
      actionsCell.appendChild(deleteBtn);

      row.appendChild(actionsCell);
      tbody.appendChild(row);
    });
  }

  function uploadTorrent(filePath, buttonElement) {
    // Show loading state
    const originalText = buttonElement.textContent;
    buttonElement.textContent = "Uploading...";
    buttonElement.disabled = true;

    fetch("/api/watcher/upload", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ path: filePath }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          showAlert("Torrent file uploaded to Seedr successfully!", "success");
          // Remove the row
          buttonElement.closest("tr").remove();

          // Check if table is now empty
          const tbody = document.getElementById("available-torrents-body");
          if (tbody.children.length === 0) {
            document.getElementById("available-torrents-table").style.display =
              "none";
            document.getElementById("no-torrents-message").style.display =
              "block";
          }

          // Refresh logs
          fetchWatcherLogs();

          // Refresh main torrents table if it exists
          if (document.getElementById("refresh-btn")) {
            document.getElementById("refresh-btn").click();
          }
        } else {
          showAlert(`Error uploading torrent: ${data.message}`, "error");
          // Reset button
          buttonElement.textContent = originalText;
          buttonElement.disabled = false;
        }
      })
      .catch((error) => {
        showAlert(`Error uploading torrent: ${error}`, "error");
        buttonElement.textContent = originalText;
        buttonElement.disabled = false;
      });
  }

  function deleteTorrentFile(filePath, buttonElement) {
    // Show loading state
    const originalText = buttonElement.textContent;
    buttonElement.textContent = "Deleting...";
    buttonElement.disabled = true;

    fetch("/api/watcher/delete-file", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ path: filePath }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          showAlert("File deleted successfully", "success");
          // Remove the row
          buttonElement.closest("tr").remove();

          // Check if table is now empty
          const tbody = document.getElementById("available-torrents-body");
          if (tbody.children.length === 0) {
            document.getElementById("available-torrents-table").style.display =
              "none";
            document.getElementById("no-torrents-message").style.display =
              "block";
          }

          // Refresh logs
          fetchWatcherLogs();
        } else {
          showAlert(`Error deleting file: ${data.message}`, "error");
          // Reset button
          buttonElement.textContent = originalText;
          buttonElement.disabled = false;
        }
      })
      .catch((error) => {
        showAlert(`Error deleting file: ${error}`, "error");
        buttonElement.textContent = originalText;
        buttonElement.disabled = false;
      });
  }

  // =============== WATCHER LOGS FUNCTIONS ===============

  function fetchWatcherLogs() {
    const loadingElement = document.getElementById("logs-loading");
    const errorElement = document.getElementById("logs-error");
    const contentElement = document.getElementById("logs-content");
    const linesCount = document.getElementById("log-lines-count")?.value || 50;

    if (!loadingElement || !errorElement || !contentElement) return;

    // Show loading, hide other elements
    loadingElement.style.display = "block";
    errorElement.style.display = "none";
    contentElement.style.display = "none";

    fetch(`/api/watcher/logs?lines=${linesCount}`)
      .then((response) => response.json())
      .then((data) => {
        loadingElement.style.display = "none";

        if (data.success) {
          if (data.logs && data.logs.length > 0) {
            // Format logs with colors for different log types
            let formattedLogs = "";
            data.logs.forEach((line) => {
              let logLine = line;

              // Add colors based on log content
              if (line.includes("Successfully") || line.includes("✅")) {
                logLine = `<span style="color: #4caf50;">${line}</span>`;
              } else if (
                line.includes("Error") ||
                line.includes("Failed") ||
                line.includes("❌")
              ) {
                logLine = `<span style="color: #c62828;">${line}</span>`;
              } else if (line.includes("[MANUAL]")) {
                logLine = `<span style="color: #1e88e5;">${line}</span>`;
              }

              formattedLogs += logLine + "\n";
            });

            contentElement.innerHTML = formattedLogs;
            contentElement.style.display = "block";

            // Scroll to bottom to show latest logs
            contentElement.scrollTop = contentElement.scrollHeight;
          } else {
            contentElement.innerHTML = "No logs found";
            contentElement.style.display = "block";
          }
        } else {
          errorElement.textContent = data.message || "Failed to fetch logs";
          errorElement.style.display = "block";
        }
      })
      .catch((error) => {
        loadingElement.style.display = "none";
        errorElement.textContent = `Error: ${error}`;
        errorElement.style.display = "block";
      });
  }

  // =============== ALERT FUNCTION ===============

  function showAlert(message, type) {
    // Create alert element
    const alertDiv = document.createElement("div");
    alertDiv.className =
      type === "success" ? "alert alert-success" : "error-message";

    // Add message
    alertDiv.textContent = message;

    // Find where to insert the alert
    const container = document.querySelector(".container");
    if (container) {
      document.body.insertBefore(alertDiv, container);
    } else {
      document.body.prepend(alertDiv);
    }

    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (document.body.contains(alertDiv)) {
        alertDiv.remove();
      }
    }, 5000);
  }

  // Make functions available globally for button click handlers
  window.uploadTorrent = uploadTorrent;
  window.deleteTorrentFile = deleteTorrentFile;
  window.fetchAvailableTorrents = fetchAvailableTorrents;
  window.fetchWatcherLogs = fetchWatcherLogs;
  window.showAlert = showAlert;

  // Function to update progress bars when refreshing data
  function updateProgressBars() {
    initializeProgressBars();
  }

  // Success page initialization
  if (document.getElementById("serverAddress")) {
    setServerInfo();
  }

  // =============== SUCCESS PAGE FUNCTIONS ===============

  function setServerInfo() {
    // Get the current URL
    const currentUrl = window.location.href;
    const baseUrl = currentUrl.split("/success")[0];
    const dashboardUrl = baseUrl + "/";

    // Display the server address
    document.getElementById("serverAddress").textContent = baseUrl;
    document.getElementById("dashboardUrl").textContent = dashboardUrl;
  }
});
