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

analyzeBtn.addEventListener("click", () => {
  statusText.textContent = "Analyzing...";
  analyzeResult.classList.remove("empty");
  analyzeResult.textContent = "Generating analysis...";

  setTimeout(() => {
    analyzeResult.innerHTML =
`
<strong>1. Summary of Defect Detection Status</strong>
- Total Bugs Found This Week: 16
- Fixed Bugs: 14
- Remaining Bugs: <span style="color:#E05759;">2</span>

<strong>2. Trend Analysis</strong>
- The number of bugs discovered was initially high, but decreased toward the end of testing.
- The lead time from discovery to fix was generally 1-2 days, and the fix cycle was also favorable.

<strong>3. Future Concerns</strong>
- Currently, many of the unfixed bugs are minor and are expected to be resolved by release.
- Continue to pay attention to the comprehensiveness of test cases and the trend of new bugs.`;

    statusText.textContent = "Last updated: just now";
  }, 800);
});

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
