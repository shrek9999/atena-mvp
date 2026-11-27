const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(root, "ai-trener.html"), "utf8");
const app = fs.readFileSync(path.join(root, "ai-trener.js"), "utf8");
const onboarding = fs.readFileSync(path.join(root, "ai-trener-onboarding.js"), "utf8");
const decisions = fs.readFileSync(path.join(root, "ai-trener-pattern-decisions.js"), "utf8");

test("the onboarding uses six guided learning modules instead of a separate movement self-assessment", () => {
  for (const pattern of ["squat", "hinge", "horizontal_push", "horizontal_pull", "vertical_push", "lunge"]) {
    assert.ok(app.includes(pattern), "Missing guided movement pattern: " + pattern);
  }
  assert.match(html, /id="movement-learning-modules"/);
  assert.match(html, /id="movement-learning-progress"/);
  assert.doesNotMatch(html, /id="movement-assessment-submit"|id="movement-assessment-consent"|data-movement-task=/);
  assert.doesNotMatch(app, /readMovementAssessment|submitMovementAssessment|movement-assessment-submit|movementAssessmentConsent|\/api\/movement-assessment/);
  assert.match(onboarding, /atena:movement-assessment-complete/);
});

test("guided learning allows temporary exclusions and teaches the actual overhead press", () => {
  assert.match(app, /Temporarily skip this pattern/);
  assert.match(app, /Return to this pattern/);
  assert.doesNotMatch(app, /Learning status /);
  assert.match(app, /exclusion_reason/);
  assert.match(app, /status === "excluded"/);
  const verticalStart = app.indexOf("    vertical_push: {", app.indexOf("const MOVEMENT_LEARNING_CHECKS = {"));
  const verticalEnd = app.indexOf("\n    },", verticalStart);
  const vertical = app.slice(verticalStart, verticalEnd);
  assert.ok(vertical.includes('title: "Overhead press (very light load)"'));
  assert.match(vertical, /Learn the actual overhead press/i);
  assert.match(vertical, /Press upwards in a smooth path/i);
  assert.match(vertical, /actual overhead press/i);
  assert.match(vertical, /very light, suitable implement/i);
  assert.match(vertical, /not a strength test/i);
  assert.doesNotMatch(app, /light_implement_press/);
  assert.match(app, /movement-learning-card-summary/);
  assert.match(app, /movement-learning-checklist-details/);
});

test("air squat always uses forward arms, with an optional light external counterweight, and demos use ATENA's channel", () => {
  const squatStart = app.indexOf("    squat: {", app.indexOf("const MOVEMENT_LEARNING_CHECKS = {"));
  const squatEnd = app.indexOf("\n    },", squatStart);
  const squat = app.slice(squatStart, squatEnd);
  assert.match(squat, /title: "Air squat"/);
  assert.match(squat, /both arms extended forwards throughout every repetition/);
  assert.match(squat, /5 air squats at tempo 3–1–1/);
  assert.match(squat, /light 1–4 kg/);
  assert.match(squat, /stable support under the heels/);
  assert.match(squat, /toes or forefoot lift/);
  assert.match(squat, /do not raise the heels/);
  assert.match(squat, /foot tripod/);
  assert.match(squat, /balance remains difficult/);
  assert.ok(squat.includes("https://youtu.be/vGu9T3FFjmc"));
  const verticalStart = app.indexOf("    vertical_push: {", app.indexOf("const MOVEMENT_LEARNING_CHECKS = {"));
  const verticalEnd = app.indexOf("\n    },", verticalStart);
  const vertical = app.slice(verticalStart, verticalEnd);
  assert.match(vertical, /Overhead press/);
  assert.ok(vertical.includes("https://youtu.be/TNiOG70LdxI"));
  assert.ok(app.includes("const demoUrl = config?.demoUrl"));
});

test("capacity-development transition is explained from repeatable training evidence", () => {
  assert.match(app, /ready_for_conservative_starting_variation/);
  assert.match(app, /Two recorded, controlled training exposures/);
});

test("session movement-focus tasks and progression guidance are visible in the plan", () => {
  assert.match(app, /session\.learningTasks\?\.length/);
  assert.match(app, /task\.method/);
  assert.match(app, /task\.description/);
  assert.match(app, /prescription\.load_guidance/);
  assert.match(app, /prescription\.variation_progression_guidance/);
});

test("symptom regression requires familiarity, movement quality and next-day response", () => {
  assert.match(app, /symptomFamiliarity/);
  assert.match(app, /symptomQualityChange/);
  assert.match(app, /symptomNextDay/);
  assert.match(app, /familiar_stable/);
  assert.match(app, /same_or_better/);
});

test("each guided movement module contains exactly six learning criteria", () => {
  const start = app.indexOf("const MOVEMENT_LEARNING_CHECKS = {");
  const end = app.indexOf("\n  function guidedLearningCount()", start);
  assert.ok(start >= 0 && end > start, "Learning criteria registry must exist");
  const registry = app.slice(start, end);
  for (const pattern of ["squat", "hinge", "horizontal_push", "horizontal_pull", "vertical_push", "lunge"]) {
    const patternStart = registry.indexOf("    " + pattern + ": {");
    assert.ok(patternStart >= 0, "Missing learning criteria for " + pattern);
    const nextPattern = registry.indexOf("\n    },", patternStart);
    const section = registry.slice(patternStart, nextPattern < 0 ? registry.length : nextPattern);
    const criteria = section.match(/^\s+\["[^"]+",\s+"/gm) || [];
    assert.equal(criteria.length, 6, pattern + " must have six criteria");
    const teaching = section.match(/steps:\s*\[([^\]]+)\]/);
    assert.ok(teaching, pattern + " must include concise teaching cues");
    assert.equal((teaching[1].match(/"/g) || []).length / 2, 3, pattern + " must have three teaching steps");
  }
});

test("learning progress is persisted separately from optional health-data consent", () => {
  assert.match(app, /\/api\/profile\/.*\/learning-progress/);
  assert.match(app, /atena\.learning\.progress/);
  assert.match(html, /id="profile-health-consent"/);
  assert.match(html, /learning checklists are saved separately and do not require this consent/);
  assert.match(html, /id="movement-camera-consent"/);
  assert.match(html, /Video stays on this device/);
  assert.match(html, /observations may accompany your plan request/);
  assert.match(html, /They are not stored/);
});


test("symptom flow does not offer a loaded press regression when shoulder symptoms are reported", () => {
  assert.match(app, /vertical_push: \[\]/);
  assert.match(app, /No loaded overhead-press regression is offered when shoulder symptoms are reported/);
  assert.match(app, /Overhead press \/ shoulder/);
  assert.match(decisions, /vertical_push: new Set\(\)/);
});


test("movement teaching uses precise exercise names and biomechanically meaningful checkpoints", () => {
  const start = app.indexOf("const MOVEMENT_LEARNING_CHECKS = {");
  const end = app.indexOf("\n  function guidedLearningCount()", start);
  const registry = app.slice(start, end);
  const squat = registry.slice(registry.indexOf("    squat: {"), registry.indexOf("\n    },", registry.indexOf("    squat: {")));
  assert.match(squat, /flexing your knees and hips simultaneously/i);
  assert.match(squat, /relatively upright/i);
  assert.match(squat, /heel lifts/i);
  assert.match(squat, /stable support under the heels/i);
  assert.match(squat, /toes begin to lift/i);
  assert.match(squat, /do not force a vertical trunk/i);

  const bendStart = registry.indexOf("    hinge: {");
  const bend = registry.slice(bendStart, registry.indexOf("\n    },", bendStart));
  assert.match(bend, /Forward bend with a neutral spine/);
  assert.match(bend, /hamstring tension/i);
  assert.match(bend, /balance/i);
  assert.doesNotMatch(bend, /Hip hinge/);

  const pushStart = registry.indexOf("    horizontal_push: {");
  const push = registry.slice(pushStart, registry.indexOf("\n    },", pushStart));
  assert.match(push, /shoulder blades move towards each other/i);
  assert.match(push, /spread them around the rib cage/i);
  assert.match(push, /elbows travel back/i);
  assert.match(push, /shoulders away from your ears/i);
  assert.match(push, /chest lowers and rises as one unit with my trunk; it does not collapse or drop ahead of my pelvis/i);

  const rowStart = registry.indexOf("    horizontal_pull: {");
  const row = registry.slice(rowStart, registry.indexOf("\n    },", rowStart));
  assert.match(row, /Bent-over row/);
  assert.match(row, /torso angle stays almost unchanged/i);
  assert.match(row, /do not rock, rotate or use momentum/i);

  const pressStart = registry.indexOf("    vertical_push: {");
  const press = registry.slice(pressStart, registry.indexOf("\n    },", pressStart));
  assert.match(press, /ribs stacked over your pelvis/i);
  assert.match(press, /rotate upwards naturally/i);

  const lungeStart = registry.indexOf("    lunge: {");
  const lunge = registry.slice(lungeStart, registry.indexOf("\n    },", lungeStart));
  assert.match(lunge, /side-to-side width for balance/i);
  assert.match(lunge, /front foot fully supported/i);

  assert.match(app, /createElement\("section"\)/);
  assert.doesNotMatch(app, /checklistDetails = document.createElement\("details"\)/);
});

test("the Slovenian language dictionary covers the revised movement modules", () => {
  const i18n = fs.readFileSync(path.join(root, "ai-trener-i18n.js"), "utf8");
  for (const phrase of [
    "Predklon z nevtralno hrbtenico", "Veslanje v predklonu", "Skleca",
    "sočasno upogibaš kolena in kolke", "zadnjih stegenskih mišic",
    "lopatici nadzorovano pomikata skupaj", "lopatici pomakni narazen",
    "Status učenja", "Kontrolne točke"
  ]) assert.ok(i18n.includes(phrase), "Missing Slovenian localization: " + phrase);
});
