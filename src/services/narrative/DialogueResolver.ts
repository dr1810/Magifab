import type { NarrativeScene } from './types'

export type ResolvedDialogueReference = { pronoun: string; entityId: string; evidence: string }

export class DialogueResolver {
  resolve(scene: NarrativeScene, priorScenes: NarrativeScene[]): ResolvedDialogueReference[] {
    return scene.dialogueReferences.flatMap((reference) => reference.pronouns.filter((pronoun) => {
      const targetMentionedNow = reference.targetEntityIds.includes(pronoun.resolvedEntityId)
      const targetKnownEarlier = priorScenes.some((prior) => prior.visualGrounding.visibleEntityIds.includes(pronoun.resolvedEntityId))
      return targetMentionedNow && (targetKnownEarlier || Boolean(pronoun.evidence))
    }).map((pronoun) => ({ pronoun: pronoun.pronoun, entityId: pronoun.resolvedEntityId, evidence: pronoun.evidence })))
  }
}
