import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const SAMPLE = readFileSync(join(here, "..", "..", "samples", "bogie_maintenance.dita"), "utf8");

// Fresh browser context ⇒ no users ⇒ Login starts in "create account" mode.
async function signIn(page: Page) {
  await page.goto("/");
  await expect(page.locator(".login-card")).toBeVisible();
  await page.locator('.field input').first().fill("Maria Ruiz"); // name
  await page.locator('.field input').nth(1).fill("maria@atexis.com"); // email
  await page.locator('.field input[type=password]').fill("pw123456");
  await page.getByRole("button", { name: /Create account/ }).click();
  await expect(page.locator(".brand")).toContainText("XML Proofreader");
}

async function loadSample(page: Page) {
  await page.evaluate((xml) => {
    (window as unknown as { __docreview: { load: (n: string, x: string) => void } })
      .__docreview.load("bogie_maintenance.dita", xml);
  }, SAMPLE);
}

async function loadXml(page: Page, name: string, xml: string) {
  await page.evaluate(
    ([n, x]) => {
      (window as unknown as { __docreview: { load: (n: string, x: string) => void } })
        .__docreview.load(n, x);
    },
    [name, xml]
  );
}

// Select a run of text in the document and pop the floating annotation toolbar.
async function selectText(page: Page, text: string) {
  await page.evaluate((t) => {
    const area = document.querySelector(".scroll-area")!;
    const walker = document.createTreeWalker(area, NodeFilter.SHOW_TEXT);
    let node: Node | null;
    while ((node = walker.nextNode())) {
      const idx = node.nodeValue!.indexOf(t);
      if (idx >= 0) {
        const r = document.createRange();
        r.setStart(node, idx);
        r.setEnd(node, idx + t.length);
        const sel = window.getSelection()!;
        sel.removeAllRanges();
        sel.addRange(r);
        node.parentElement!.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
        return;
      }
    }
    throw new Error("text not found in document: " + t);
  }, text);
}

const MINI = `<?xml version="1.0" encoding="UTF-8"?>
<task id="t"><title>Mini task</title><taskbody><context><p>Tighten the bolt to 120 Nm before service.</p></context></taskbody></task>`;

const THREAD = `<?xml version="1.0" encoding="UTF-8"?>
<task id="t"><title>Threaded</title><taskbody><context><p><?oxy_comment_start author="Ana" timestamp="20260101T090000+0000" comment="Root note" id="root_a_1"?><?oxy_comment_start author="Bea" timestamp="20260101T091000+0000" parentID="root_a_1" comment="First reply" mid="1"?>shared text<?oxy_comment_end mid="1"?><?oxy_comment_end?></p></context></taskbody></task>`;

test("local sign-in then empty document state", async ({ page }) => {
  await signIn(page);
  await expect(page.locator(".empty-doc")).toContainText("No document open");
  await expect(page.locator(".ccard")).toHaveCount(0);
});

test("renders a loaded document with highlights and comments", async ({ page }) => {
  await signIn(page);
  await loadSample(page);
  await expect(page.locator(".doc-title")).toContainText("Motor Bogie Maintenance");
  await expect(page.locator(".ccard")).toHaveCount(2);
  await expect(page.locator(".hl").first()).toBeVisible();
});

test("switches to the XML source view", async ({ page }) => {
  await signIn(page);
  await loadSample(page);
  await page.getByRole("button", { name: /XML view/ }).click();
  await expect(page.locator(".cm-editor")).toBeVisible();
});

test("opens per-user settings", async ({ page }) => {
  await signIn(page);
  await page.locator(".userbtn").click();
  await page.getByRole("button", { name: /Settings/ }).click();
  await expect(page.locator(".modal h3")).toContainText("Settings");
  await expect(page.locator(".set-tabs")).toBeVisible();
});

test("renders a pre-existing thread with nested replies", async ({ page }) => {
  await signIn(page);
  await loadXml(page, "thread.dita", THREAD);
  await expect(page.locator(".ccard")).toHaveCount(1);
  await expect(page.locator(".cnode.is-reply")).toHaveCount(1);
  await expect(page.locator(".cnode.is-reply")).toContainText("First reply");
});

test("create a comment, reply, then resolve and reopen the reply", async ({ page }) => {
  await signIn(page);
  await loadXml(page, "mini.dita", MINI);

  // Create a comment from a text selection.
  await selectText(page, "bolt");
  await page.locator(".float-tb").getByRole("button", { name: /Comment/ }).click();
  const editor = page.locator(".ccard textarea");
  await expect(editor).toBeVisible();
  await editor.fill("Please verify the torque value");
  await page.locator(".ccard .actions").getByRole("button", { name: "Save" }).click();
  await expect(page.locator(".ccard")).toContainText("Please verify the torque value");

  // Reply to it (converts the simple comment into a thread root).
  await page.locator(".reply-link").click();
  await page.locator(".reply-box textarea").fill("Agreed, it should be 130 Nm");
  await page.locator(".reply-box").getByRole("button", { name: "Send" }).click();
  await expect(page.locator(".cnode.is-reply")).toHaveCount(1);
  await expect(page.locator(".cnode.is-reply")).toContainText("Agreed, it should be 130 Nm");

  // Resolve the reply, then reopen it.
  const reply = page.locator(".cnode.is-reply");
  await reply.getByRole("button", { name: /Resolve/ }).click();
  await expect(reply.getByRole("button", { name: /Reopen/ })).toBeVisible();
  await expect(reply.locator(".status-tag.done")).toBeVisible();
  await reply.getByRole("button", { name: /Reopen/ }).click();
  await expect(reply.getByRole("button", { name: /Resolve/ })).toBeVisible();
});
