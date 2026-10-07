const stageContent = {
  select: {
    kicker: "01 · HERMES",
    title: "Resolve the ready frontier",
    body: "Read the project tracker first. Choose one authorized, unclaimed outcome. Stop cleanly when nothing is ready instead of buying a repository-wide scan.",
    input: "tracker + accepted intent",
    output: "one owned outcome",
  },
  frame: {
    kicker: "02 · DATACRAFT PM",
    title: "Frame one useful outcome",
    body: "Give the working session the accepted intent, current revision, dependencies, authorization limits, and the checks that will establish the result.",
    input: "owned outcome + project state",
    output: "bounded execution graph",
  },
  delegate: {
    kicker: "03 · RINGER",
    title: "Dispatch only ready work",
    body: "Each worker gets owned paths, a self-contained brief, an expected artifact, and an executable gate. Independent work can run in isolated directories or worktrees.",
    input: "manifest + frozen brief",
    output: "isolated CLI attempts",
  },
  gate: {
    kicker: "04 · RINGER",
    title: "Run the contract",
    body: "Ringer executes the declared check against the worker artifact. Failure output feeds one bounded retry. PASS comes from the gate, never the worker’s summary.",
    input: "artifact + check command",
    output: "verdict + durable receipt",
  },
  integrate: {
    kicker: "05 · DATACRAFT PM",
    title: "Integrate and accept",
    body: "The accountable session inspects scope, joins work in dependency order, runs combined checks, and evaluates the delivered outcome against its accepted evidence requirements.",
    input: "verified worker output",
    output: "integrated evidence",
  },
  continue: {
    kicker: "06 · HERMES",
    title: "Record, recompute, continue",
    body: "Update the tracker, preserve the receipt, and recompute the frontier. Dispatch the next authorized ticket—or bring Joe one concise decision when judgment is actually required.",
    input: "result + project record",
    output: "next work or one decision",
  },
};

const stageDetail = document.querySelector("[data-stage-detail]");
const stageTabs = document.querySelectorAll("[data-stage]");

stageTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    const next = stageContent[tab.dataset.stage];
    stageTabs.forEach((item) => {
      const active = item === tab;
      item.classList.toggle("is-active", active);
      item.setAttribute("aria-selected", String(active));
    });

    stageDetail.innerHTML = `
      <p class="stage-kicker">${next.kicker}</p>
      <h3>${next.title}</h3>
      <p>${next.body}</p>
      <div class="stage-contract">
        <span>INPUT</span><code>${next.input}</code>
        <span>OUTPUT</span><code>${next.output}</code>
      </div>
    `;
  });
});
