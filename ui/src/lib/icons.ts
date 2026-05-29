// Registro Iconify: cada icono Phosphor light usado en la UI se importa una sola vez
// aquí y se registra con addIcon() para que el wrapper <Icon> lo resuelva por nombre.
//
// Convención (igual que todoconta-apps/web): Phosphor termina en -light (stroke 1.5px).
//
// Para agregar un icono:
//   1. import del JSON desde @iconify-icons/ph/<name>-light
//   2. addIcon("ph:<name>-light", <importedJson>)
//   3. usar en JSX: <Icon icon="ph:<name>-light" className="..." />

import { addIcon } from '@iconify/react';

import arrowCounterClockwise from '@iconify-icons/ph/arrow-counter-clockwise-light';
import arrowDown from '@iconify-icons/ph/arrow-down-light';
import arrowLeft from '@iconify-icons/ph/arrow-left-light';
import arrowUp from '@iconify-icons/ph/arrow-up-light';
import arrowsClockwise from '@iconify-icons/ph/arrows-clockwise-light';
import arrowsDownUp from '@iconify-icons/ph/arrows-down-up-light';
import buildings from '@iconify-icons/ph/buildings-light';
import calendar from '@iconify-icons/ph/calendar-light';
import calendarCheck from '@iconify-icons/ph/calendar-check-light';
import caretDown from '@iconify-icons/ph/caret-down-light';
import caretRight from '@iconify-icons/ph/caret-right-light';
import caretUp from '@iconify-icons/ph/caret-up-light';
import check from '@iconify-icons/ph/check-light';
import checkCircle from '@iconify-icons/ph/check-circle-light';
import circleNotch from '@iconify-icons/ph/circle-notch-light';
import clipboardText from '@iconify-icons/ph/clipboard-text-light';
import clockCounterClockwise from '@iconify-icons/ph/clock-counter-clockwise-light';
import currencyDollar from '@iconify-icons/ph/currency-dollar-light';
import database from '@iconify-icons/ph/database-light';
import downloadSimple from '@iconify-icons/ph/download-simple-light';
import eye from '@iconify-icons/ph/eye-light';
import file from '@iconify-icons/ph/file-light';
import filePdf from '@iconify-icons/ph/file-pdf-light';
import fileText from '@iconify-icons/ph/file-text-light';
import folder from '@iconify-icons/ph/folder-light';
import folderOpen from '@iconify-icons/ph/folder-open-light';
import folders from '@iconify-icons/ph/folders-light';
import gear from '@iconify-icons/ph/gear-light';
import hardDrives from '@iconify-icons/ph/hard-drives-light';
import key from '@iconify-icons/ph/key-light';
import lock from '@iconify-icons/ph/lock-light';
import magnifyingGlass from '@iconify-icons/ph/magnifying-glass-light';
import packageIcon from '@iconify-icons/ph/package-light';
import pencilSimple from '@iconify-icons/ph/pencil-simple-light';
import plus from '@iconify-icons/ph/plus-light';
import prohibit from '@iconify-icons/ph/prohibit-light';
import scroll from '@iconify-icons/ph/scroll-light';
import sealCheck from '@iconify-icons/ph/seal-check-light';
import shieldCheck from '@iconify-icons/ph/shield-check-light';
import squaresFour from '@iconify-icons/ph/squares-four-light';
import trash from '@iconify-icons/ph/trash-light';
import uploadSimple from '@iconify-icons/ph/upload-simple-light';
import warning from '@iconify-icons/ph/warning-light';
import warningCircle from '@iconify-icons/ph/warning-circle-light';
import x from '@iconify-icons/ph/x-light';
import xCircle from '@iconify-icons/ph/x-circle-light';

addIcon('ph:arrow-counter-clockwise-light', arrowCounterClockwise);
addIcon('ph:arrow-down-light', arrowDown);
addIcon('ph:arrow-left-light', arrowLeft);
addIcon('ph:arrow-up-light', arrowUp);
addIcon('ph:arrows-clockwise-light', arrowsClockwise);
addIcon('ph:arrows-down-up-light', arrowsDownUp);
addIcon('ph:buildings-light', buildings);
addIcon('ph:calendar-light', calendar);
addIcon('ph:calendar-check-light', calendarCheck);
addIcon('ph:caret-down-light', caretDown);
addIcon('ph:caret-right-light', caretRight);
addIcon('ph:caret-up-light', caretUp);
addIcon('ph:check-light', check);
addIcon('ph:check-circle-light', checkCircle);
addIcon('ph:circle-notch-light', circleNotch);
addIcon('ph:clipboard-text-light', clipboardText);
addIcon('ph:clock-counter-clockwise-light', clockCounterClockwise);
addIcon('ph:currency-dollar-light', currencyDollar);
addIcon('ph:database-light', database);
addIcon('ph:download-simple-light', downloadSimple);
addIcon('ph:eye-light', eye);
addIcon('ph:file-light', file);
addIcon('ph:file-pdf-light', filePdf);
addIcon('ph:file-text-light', fileText);
addIcon('ph:folder-light', folder);
addIcon('ph:folder-open-light', folderOpen);
addIcon('ph:folders-light', folders);
addIcon('ph:gear-light', gear);
addIcon('ph:hard-drives-light', hardDrives);
addIcon('ph:key-light', key);
addIcon('ph:lock-light', lock);
addIcon('ph:magnifying-glass-light', magnifyingGlass);
addIcon('ph:package-light', packageIcon);
addIcon('ph:pencil-simple-light', pencilSimple);
addIcon('ph:plus-light', plus);
addIcon('ph:prohibit-light', prohibit);
addIcon('ph:scroll-light', scroll);
addIcon('ph:seal-check-light', sealCheck);
addIcon('ph:shield-check-light', shieldCheck);
addIcon('ph:squares-four-light', squaresFour);
addIcon('ph:trash-light', trash);
addIcon('ph:upload-simple-light', uploadSimple);
addIcon('ph:warning-light', warning);
addIcon('ph:warning-circle-light', warningCircle);
addIcon('ph:x-light', x);
addIcon('ph:x-circle-light', xCircle);
