/**
 * IndexedDB-backed queue for review events that could not reach the server
 * (e.g. when the device is offline or the network is unreachable).
 *
 * Queued reviews are replayed in insertion order when the network is restored.
 * Each pending review is stored as a plain object:
 *   { object_id, quality, review_state, queued_at }
 *
 * Exports
 * ───────
 *   queueReview(review)       Save a review for later retry.
 *   getPendingReviews()       Return all queued reviews as [{key, value}].
 *   deleteReview(key)         Remove a successfully synced review.
 *   countPendingReviews()     Return the number of queued reviews.
 */

const DB_NAME    = 'mnemosyne-offline';
const DB_VERSION = 1;
const STORE      = 'pending-reviews';

/** Singleton DB connection promise — opened once, reused on every call. */
let _dbPromise = null;

function openDb() {
  if (_dbPromise) return _dbPromise;
  _dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { autoIncrement: true });
      }
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = ()  => reject(req.error);
  });
  return _dbPromise;
}

/** Append a review to the pending queue.  Returns the assigned IDB key. */
export async function queueReview(review) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction(STORE, 'readwrite');
    const store = tx.objectStore(STORE);
    const req   = store.add(review);
    req.onsuccess = () => resolve(req.result);
    req.onerror   = ()  => reject(req.error);
  });
}

/** Return every pending review as an array of {key, value} objects. */
export async function getPendingReviews() {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx      = db.transaction(STORE, 'readonly');
    const store   = tx.objectStore(STORE);
    const entries = [];
    const req     = store.openCursor();
    req.onsuccess = e => {
      const cursor = e.target.result;
      if (cursor) {
        entries.push({ key: cursor.key, value: cursor.value });
        cursor.continue();
      } else {
        resolve(entries);
      }
    };
    req.onerror = () => reject(req.error);
  });
}

/** Remove a single pending review by its IDB key (call after a successful sync). */
export async function deleteReview(key) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction(STORE, 'readwrite');
    const store = tx.objectStore(STORE);
    const req   = store.delete(key);
    req.onsuccess = () => resolve();
    req.onerror   = ()  => reject(req.error);
  });
}

/** Return the number of reviews currently queued (cheap IDB count). */
export async function countPendingReviews() {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction(STORE, 'readonly');
    const store = tx.objectStore(STORE);
    const req   = store.count();
    req.onsuccess = () => resolve(req.result);
    req.onerror   = ()  => reject(req.error);
  });
}
