import type { CitationItem } from "../types/chat";

import type { ConversationState } from "./storeTypes";

import {

  emptyReactStepLimitTurn,

  recordReactStepLimitTurn,

} from "./reactStepLimit";



/** 为新的一轮 QA 追加空 turn 槽位并清空当前 trace */

export function beginNewQaTurn(state: ConversationState): Partial<ConversationState> {

  return {

    citationTurns: [...state.citationTurns, []],

    toolTraceTurns: [...state.toolTraceTurns, []],

    reactStepLimitTurns: [...state.reactStepLimitTurns, emptyReactStepLimitTurn()],

    citations: [],

    toolTraceLog: [],

    reactHitStepLimit: false,

  };

}



export function applyCitationToTurn(

  state: ConversationState,

  items: CitationItem[],

): Partial<ConversationState> {

  const turns = [...state.citationTurns];

  if (turns.length === 0) {

    turns.push([]);

  }

  turns[turns.length - 1] = items;

  return { citationTurns: turns, citations: items };

}



export function appendToolTraceToTurn(

  state: ConversationState,

  line: string,

): Partial<ConversationState> {

  const toolTraceLog = [...state.toolTraceLog, line];

  const turns = [...state.toolTraceTurns];

  if (turns.length === 0) {

    turns.push([]);

  }

  turns[turns.length - 1] = [...(turns[turns.length - 1] ?? []), line];

  return { toolTraceTurns: turns, toolTraceLog };

}



export function applyReactStepLimitToTurn(

  state: ConversationState,

  hit: boolean,

): Partial<ConversationState> {

  const reactStepLimitTurns = recordReactStepLimitTurn(

    state.reactStepLimitTurns,

    hit,

  );

  return {

    reactStepLimitTurns,

    reactHitStepLimit: hit,

  };

}



export function finalizeTurnTrace(state: ConversationState): Partial<ConversationState> {

  const turns = [...state.citationTurns];

  const traceTurns = [...state.toolTraceTurns];

  if (turns.length === 0 && state.citations.length > 0) {

    turns.push([...state.citations]);

  } else if (turns.length > 0) {

    turns[turns.length - 1] = [...state.citations];

  }

  if (traceTurns.length === 0 && state.toolTraceLog.length > 0) {

    traceTurns.push([...state.toolTraceLog]);

  } else if (traceTurns.length > 0) {

    traceTurns[traceTurns.length - 1] = [...state.toolTraceLog];

  }

  return { citationTurns: turns, toolTraceTurns: traceTurns };

}

