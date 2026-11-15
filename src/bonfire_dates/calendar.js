// Applies a batch of changes to one calendar through EventKit, which is far
// faster than scripting Calendar.app and can pin an event's location on a map.
//
// stdin: {"calendar": name, "ops": [{op: "check"} | {op: "upsert", …} | {op: "remove", uid}]}
// stdout: one JSON line per op, written as soon as that op is done, so a run
// cut short still reports what it finished: {"ok": true, "uid": …} or {"ok": false, "error": …}
//
// Safety: only events in the named calendar are ever changed. An ID that turns
// up in any other calendar is refused, never edited or removed.
//
// Each event carries its key in its URL (bonfire-dates:<key>). Before
// creating one, the calendar is searched for that key, so a write whose reply
// was lost (a run cut short) is found and updated, never made twice.
// Data never goes into the script text, so titles can't break or inject anything.
ObjC.import('Foundation');
ObjC.import('EventKit');
ObjC.import('MapKit');

// JXA doesn't expose CLLocation by name; MapKit has loaded the class.
const CLLocation = $.NSClassFromString('CLLocation');

const FULL_ACCESS = 3;

function readStdin() {
  const data = $.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile;
  return $.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding).js;
}

function emit(obj) {
  const line = $.NSString.alloc.initWithUTF8String(JSON.stringify(obj) + '\n');
  $.NSFileHandle.fileHandleWithStandardOutput.writeData(line.dataUsingEncoding($.NSUTF8StringEncoding));
}

function waitFor(isDone, seconds) {
  const until = Date.now() + seconds * 1000;
  while (!isDone() && Date.now() < until) {
    $.NSRunLoop.currentRunLoop.runUntilDate($.NSDate.dateWithTimeIntervalSinceNow(0.1));
  }
  return isDone();
}

function status() {
  return Number($.EKEventStore.authorizationStatusForEntityType($.EKEntityTypeEvent));  // a wrapped number otherwise
}

// Full access, asking once if need be (macOS shows its own prompt).
function ensureAccess() {
  if (status() === FULL_ACCESS) return null;
  let answered = false;
  $.EKEventStore.alloc.init.requestFullAccessToEventsWithCompletion(function () { answered = true; });
  waitFor(function () { return answered; }, 120);
  if (status() === FULL_ACCESS) return null;
  return 'no full calendar access: allow it in System Settings → Privacy & Security → Calendars';
}

function findCalendar(store, name) {
  const cals = store.calendarsForEntityType($.EKEntityTypeEvent).js;
  for (let i = 0; i < cals.length; i++) {
    if (cals[i].title.js === name) return cals[i];
  }
  return null;
}

// The event with this ID in our calendar; throws if it exists only elsewhere.
function findEvent(store, cal, uid) {
  if (!uid) return null;
  const mine = cal.calendarIdentifier.js;
  const items = store.calendarItemsWithExternalIdentifier(uid).js;
  let elsewhere = false;
  for (let i = 0; i < items.length; i++) {
    if (items[i].calendar.calendarIdentifier.js === mine) return items[i];
    elsewhere = true;
  }
  if (elsewhere) throw new Error('event ' + uid + ' is in another calendar: refusing to touch it');
  return null;
}

const MARK = 'bonfire-dates:';
const DAY_S = 24 * 3600;

// Our events (in our calendar only) starting between two times, in seconds since 1970.
function eventsBetween(store, cal, from, to) {
  const pred = store.predicateForEventsWithStartDateEndDateCalendars(
    $.NSDate.dateWithTimeIntervalSince1970(from), $.NSDate.dateWithTimeIntervalSince1970(to), $([cal]));
  return store.eventsMatchingPredicate(pred).js;
}

function markOf(ev) {
  return ev.URL && !ev.URL.isNil() ? ev.URL.absoluteString.js : '';
}

// An event already written for this key: within a year either side of its
// start, as a moved night keeps its key.
function findByKey(store, cal, key, start) {
  if (!key) return null;
  const want = MARK + encodeURIComponent(key);
  const found = eventsBetween(store, cal, start - 366 * DAY_S, start + 366 * DAY_S)
    .filter(function (ev) { return markOf(ev) === want; });
  return found.length ? found[0] : null;
}

// Every event in our calendar between two times, with both IDs.
function list(store, cal, req) {
  return eventsBetween(store, cal, req.from, req.to).map(function (ev) {
    return { uid: ev.calendarItemExternalIdentifier.js, local: ev.calendarItemIdentifier.js, title: ev.title.js,
             start: Number(ev.startDate.timeIntervalSince1970), mark: markOf(ev) };
  });
}

// A pin for a place we have no coordinates for, from Maps. null if none in time.
function lookUp(text) {
  const request = $.MKLocalSearchRequest.alloc.init;
  request.naturalLanguageQuery = text;
  let done = false, found = null;
  $.MKLocalSearch.alloc.initWithRequest(request).startWithCompletionHandler(function (response, error) {
    if (response && !response.isNil() && response.mapItems.count > 0) {
      found = response.mapItems.objectAtIndex(0).placemark.location;
    }
    done = true;
  });
  waitFor(function () { return done; }, 8);
  return found;
}

function setLocation(ev, req) {
  if (!req.location) {
    ev.structuredLocation = $();
    ev.location = $();
    return;
  }
  const where = $.EKStructuredLocation.locationWithTitle(req.location);
  const pin = req.geo
    ? CLLocation.alloc.initWithLatitudeLongitude(req.geo[0], req.geo[1])
    : lookUp(req.location);
  if (pin && !pin.isNil()) where.geoLocation = pin;
  ev.structuredLocation = where;
}

function upsert(store, cal, req) {
  let ev = findEvent(store, cal, req.uid) || findByKey(store, cal, req.key, req.start / 1000);
  if (!ev) {
    ev = $.EKEvent.eventWithEventStore(store);
    ev.calendar = cal;
  }
  ev.title = req.title;
  ev.allDay = !!req.allDay;  // all-day events run from local midnight to the next
  ev.startDate = $.NSDate.dateWithTimeIntervalSince1970(req.start / 1000);
  ev.endDate = $.NSDate.dateWithTimeIntervalSince1970(req.end / 1000);
  ev.notes = req.notes;
  if (req.key) ev.URL = $.NSURL.URLWithString(MARK + encodeURIComponent(req.key));
  setLocation(ev, req);
  ev.alarms = $();
  req.alarms.forEach(function (mins) { ev.addAlarm($.EKAlarm.alarmWithRelativeOffset(mins * 60)); });
  const error = Ref();
  if (!store.saveEventSpanCommitError(ev, $.EKSpanThisEvent, true, error)) {
    throw new Error('save failed: ' + (error[0] ? error[0].localizedDescription.js : 'unknown'));
  }
  return ev.calendarItemExternalIdentifier.js;
}

function remove(store, cal, req) {
  const ev = findEvent(store, cal, req.uid);
  if (!ev) return req.uid;  // already gone
  const error = Ref();
  if (!store.removeEventSpanCommitError(ev, $.EKSpanThisEvent, true, error)) {
    throw new Error('remove failed: ' + (error[0] ? error[0].localizedDescription.js : 'unknown'));
  }
  return req.uid;
}

function run() {
  const req = JSON.parse(readStdin());
  const denied = ensureAccess();
  const store = denied ? null : $.EKEventStore.alloc.init;
  const cal = store ? findCalendar(store, req.calendar) : null;
  req.ops.forEach(function (op) {
    if (denied) return emit({ ok: false, error: denied });
    if (!cal) return emit({ ok: false, error: 'missing' });
    try {
      if (op.op === 'check') return emit({ ok: true, uid: '' });
      if (op.op === 'list') return emit({ ok: true, uid: '', events: list(store, cal, op) });
      if (op.op === 'remove') return emit({ ok: true, uid: remove(store, cal, op) });
      return emit({ ok: true, uid: upsert(store, cal, op) });
    } catch (e) {
      emit({ ok: false, error: String(e.message || e) });
    }
  });
  return '';
}
