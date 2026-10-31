const $ = (id) => document.getElementById(id);
let token = sessionStorage.getItem("pf-token"), mode = "login", timer, txs = [];
const money = (n) => "₹" + Number(n).toLocaleString("en-IN");
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cap = (s) => s[0].toUpperCase() + s.slice(1);
const say = (text, ok) => { $("msg").textContent = text; $("msg").className = "msg " + (ok ? "good" : "err"); };

// One helper for every call: attaches the login token and turns errors into messages
async function api(path, method = "GET", body) {
  const res = await fetch("/api/" + path, {
    method, body: body && JSON.stringify(body),
    headers: { "Content-Type": "application/json", ...(token && { Authorization: "Bearer " + token }) },
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && token) { logout(data.error); throw new Error(data.error); }
  if (!res.ok) throw new Error(data.error || "Something went wrong.");
  return data;
}

// ---------- Login / register ----------
$("toggleAuth").addEventListener("click", () => {
  mode = mode === "login" ? "register" : "login";
  const reg = mode === "register";
  $("authTitle").textContent = reg ? "Create account" : "Log in";
  $("authForm").querySelector(".btn").textContent = reg ? "Create account" : "Log in";
  $("toggleAuth").textContent = reg ? "Have an account? Log in" : "New here? Create an account";
  $("nameWrap").hidden = !reg; $("name").required = reg; $("authMsg").textContent = "";
});
$("authForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const d = await api(mode, "POST", { name: $("name").value, email: $("email").value, password: $("password").value });
    token = d.token; sessionStorage.setItem("pf-token", token); $("authForm").reset(); start();
  } catch (err) { $("authMsg").textContent = err.message; }
});
function logout(reason) {
  token = null; sessionStorage.removeItem("pf-token"); clearInterval(timer);
  $("app").hidden = true; $("auth").hidden = false; $("authMsg").textContent = reason || "";
}
$("logout").addEventListener("click", () => logout());

// ---------- Load & render (refreshes every 2s so status changes appear live) ----------
async function refresh() {
  try {
    const [me, bens, list] = await Promise.all([api("me"), api("beneficiaries"), api("transactions")]);
    txs = list;
    $("who").textContent = `${me.name} · A/C ${me.accountNo}`;
    $("balance").textContent = money(me.balance);
    const picked = $("toSelect").value;
    $("toSelect").innerHTML = bens.length
      ? bens.map((b) => `<option value="${b.id}">${esc(b.name)} (•••• ${b.acc.slice(-4)})</option>`).join("")
      : `<option value="">Add a beneficiary first</option>`;
    $("toSelect").value = picked;
    $("benList").innerHTML = bens.length
      ? bens.map((b) => `<li><span>${esc(b.name)}<small>•••• ${b.acc.slice(-4)}</small></span>
          <button class="link" data-del="${b.id}">Remove</button></li>`).join("")
      : `<li>No beneficiaries yet. Add one above to start sending money.</li>`;
    renderTx();
  } catch {}
}
function renderTx() {
  const f = $("filter").value, rows = txs.filter((t) => f === "all" || t.status === f);
  $("txBody").innerHTML = rows.length
    ? rows.map((t) => `<tr><td>${new Date(t.date).toLocaleString("en-IN")}</td><td>${esc(t.name)}</td>
        <td>${esc(t.note || "–")}</td>
        <td class="amt ${t.type}">${t.type === "credit" ? "+" : "−"}${money(t.amount)}</td>
        <td><span class="badge ${t.status}">${cap(t.status)}</span></td></tr>`).join("")
    : `<tr><td colspan="5">No transactions to show.</td></tr>`;
}
function start() {
  $("auth").hidden = true; $("app").hidden = false; say("");
  refresh(); clearInterval(timer); timer = setInterval(refresh, 2000);
}

// ---------- Actions ----------
const run = (fn, ok) => async (e) => {
  e.preventDefault();
  try { const r = await fn(); e.target.reset(); say(ok(r), true); refresh(); } catch (err) { say(err.message, false); }
};
$("benForm").addEventListener("submit", run(
  () => api("beneficiaries", "POST", { name: $("benName").value, acc: $("benAcc").value }), () => "Beneficiary added."));
$("transferForm").addEventListener("submit", run(
  () => api("transfer", "POST", { beneficiaryId: $("toSelect").value, amount: $("amount").value, note: $("note").value }),
  (t) => `${money(t.amount)} sent to ${t.name}. Tracking status below.`));
$("depositForm").addEventListener("submit", run(
  () => api("deposit", "POST", { amount: $("depAmount").value }), () => "Money added to your wallet."));
$("benList").addEventListener("click", async (e) => {
  if (e.target.dataset.del) { await api("beneficiaries/" + e.target.dataset.del, "DELETE"); refresh(); }
});
$("filter").addEventListener("change", renderTx);

if (token) start();
