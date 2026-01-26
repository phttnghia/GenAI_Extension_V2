let dashboard;

tableau.extensions.initializeAsync().then(() => {
  dashboard = tableau.extensions.dashboardContent.dashboard;
  console.log("✅ Tableau Extension initialized");
}).catch(err => {
  console.error("❌ Tableau init failed", err);
});


async function getAllFilters() {
  const filters = {};

  for (const ws of dashboard.worksheets) {
    const wsFilters = await ws.getFiltersAsync();
    wsFilters.forEach(f => {
      filters[f.fieldName] = f.appliedValues.map(v => v.value);
    });
  }

  return filters;
}

async function getAllWorksheetData() {
  const allData = {};

  for (const ws of dashboard.worksheets) {
    const summary = await ws.getSummaryDataAsync({ maxRows: 0 });
    const cols = summary.columns.map(c => c.fieldName);

    const rows = summary.data.map(row =>
      Object.fromEntries(
        cols.map((c, i) => [c, row[i].value])
      )
    );

    allData[ws.name] = rows;
  }

  return allData;
}


// Tab switching
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));

    tab.classList.add("active");
    document.getElementById(tab.dataset.tab).classList.add("active");
  });
});

// Analyze Report - hardcoded output
const analyzeBtn = document.getElementById("analyzeBtn");
const analyzeResult = document.getElementById("analyzeResult");
const statusText = document.getElementById("statusText");

analyzeBtn.addEventListener("click", async () => {
  try {
    statusText.textContent = "Collecting dashboard data...";
    analyzeResult.classList.remove("empty");
    analyzeResult.textContent = "Preparing data for AI analysis...";

    const filters = await getAllFilters();
    const charts = await getAllWorksheetData();

    const payload = {
      dashboard: dashboard.name,
      exported_at: new Date().toISOString(),
      filters,
      charts
    };

    console.log(
      "📦 FINAL PAYLOAD:",
      JSON.stringify(payload, null, 2)
    );


    // Gửi sang backend
    const res = await fetch("http://localhost:5000/ask-ai", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: "Analyze current dashboard state",
        context_data: payload
      })
    });

    const result = await res.json();

    analyzeResult.innerHTML = result.answer;
    statusText.textContent = "Analysis completed";

  } catch (err) {
    console.error(err);
    analyzeResult.textContent = "Failed to analyze dashboard data.";
    statusText.textContent = "Error";
  }
});

// analyzeBtn.addEventListener("click", () => {
//   statusText.textContent = "Analyzing...";
//   analyzeResult.classList.remove("empty");
//   analyzeResult.textContent = "Generating analysis...";

//   setTimeout(() => {
//     analyzeResult.innerHTML =
// `
// <strong>1. Summary of Defect Detection Status</strong>
// - Total Bugs Found This Week: 16
// - Fixed Bugs: 14
// - Remaining Bugs: <span style="color:#E05759;">2</span>

// <strong>2. Trend Analysis</strong>
// - The number of bugs discovered was initially high, but decreased toward the end of testing.
// - The lead time from discovery to fix was generally 1-2 days, and the fix cycle was also favorable.

// <strong>3. Future Concerns</strong>
// - Currently, many of the unfixed bugs are minor and are expected to be resolved by release.
// - Continue to pay attention to the comprehensiveness of test cases and the trend of new bugs.`;

//     statusText.textContent = "Last updated: just now";
//   }, 800);
// });

// Chatbox logic (overwrite mode)
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const chatResult = document.getElementById("chatResult");
const charCount = document.getElementById("charCount");

chatInput.addEventListener("input", () => {
  const length = chatInput.value.length;
  charCount.textContent = `${length} / 500`;
  sendBtn.disabled = length === 0 || length > 500;
});

sendBtn.addEventListener("click", () => {
  chatResult.classList.remove("empty");
  chatResult.textContent = "Generating response...";

  // What should the team focus on next to improve product quality?
  setTimeout(() => {
    chatResult.textContent =
      `The dashboard indicates that defect detection efficiency has improved over time, but test coverage consistency varies across components.
    To further improve product quality, the team should prioritize expanding automated regression test coverage and closely monitor modules with recurring low-severity defects, as they may indicate underlying design weaknesses.
    Additionally, maintaining a focus on reducing the lead time from defect discovery to resolution will help ensure timely fixes and overall product stability.`;
  }, 800);
});
