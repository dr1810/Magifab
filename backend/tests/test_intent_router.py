from services.intent_router import SemanticIntentRouter


class RouteEmbeddings:
    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text):
        lowered = text.casefold()
        return (
            float(any(term in lowered for term in ("meaning", "definition", "latin", "term", "name"))),
            float(any(term in lowered for term in ("who", "character", "people", "want"))),
            float(any(term in lowered for term in ("earlier", "before", "when", "timeline"))),
        )


def test_definition_route_retrieves_glossary_dialogue_and_paragraphs():
    route = SemanticIntentRouter(RouteEmbeddings()).route("What is the latin name Ellie says?")

    assert route.intent == "definition"
    assert route.evidence_kinds == ("glossary", "dialogue", "paragraph", "lore")


def test_character_route_retrieves_people_motivations_and_dialogue():
    route = SemanticIntentRouter(RouteEmbeddings()).route("What did the other two want?")

    assert route.intent == "character"
    assert route.evidence_kinds == ("character", "relationship", "dialogue", "event")


def test_timeline_route_retrieves_prior_story_evidence():
    route = SemanticIntentRouter(RouteEmbeddings()).route("What happened before this?")

    assert route.intent == "timeline"
    assert route.evidence_kinds == ("timeline", "event", "scene", "paragraph")
