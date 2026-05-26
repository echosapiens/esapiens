# E.sapiens Architecture — Mermaid Flow Diagrams

> **How to view:** Paste any code block below into [mermaid.live](https://mermaid.live) or any Markdown previewer with Mermaid support.

---

## 1. Full System Overview

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        Browser([Browser / React UI])
        Gradio([Gradio Chat UI])
    end

    subgraph VPS["VPS — Hostinger Ubuntu 22.04"]
        subgraph FastAPI["FastAPI (port 8000)"]
            AuthRouter["/api/auth/*"]
            UploadRouter["/api/upload"]
            ChatRouter["/api/chat, /api/chat/stream"]
            SessionRouter["/api/sessions/*"]
            HealthCheck["GET /health"]
        end

        subgraph AgentRuntime["Agent Runtime"]
            direction TB
            TierClassifier["classify_tier()"]
            DirectPath["direct_llm_response()"]
            ReActLoop["LangGraph ReAct Loop"]
        end

        subgraph Storage["SQLite + WAL"]
            SessionStore[("sessions")]
            MessageStore[("messages")]
            WorkspaceFS["Workspace FS"]
        end

        subgraph Tools["Tool Layer"]
            LocalTools["Local Tools\n(download_pdb, search_literature,\nplotly_plot, execute_python, etc.)"]
            DynamicTools["Dynamic Tools\n(create_tool / create_modal_tool)"]
            BioContainerJobs["Modal Dispatch\n(run_modal_job)"]
        end

        subgraph Skills["Skill System"]
            IntentClassifier["IntentClassifier\n(intent_classifier.py)"]
            SkillLoader["SkillLoader + SkillContextBuilder\n(skill_loader.py)"]
            BioSkillsDir["bioSkills/ — 26 domains\n(sequence-io, variant-calling,\npathway-analysis, etc.)"]
        end

        LLM["OpenRouter\n(DeepSeek/Exacto)\nBase URL: openrouter.ai/api/v1"]
    end

    subgraph Cloud["Cloud Services"]
        Modal["Modal.com\n(BioContainers: STAR, SRA,\nDESeq2, Bioconductor)"]
        RCSB["RCSB PDB\n(files.rcsb.org)"]
        NCBI["NCBI / PubMed\n(eutils.ncbi.nlm.nih.gov)"]
        GDC["TCGA GDC API"]
        ArXiv["arXiv API"]
    end

    Browser -->|"HTTPS + SSE"| FastAPI
    Gradio -->|"internal"| FastAPI

    FastAPI --> AuthRouter
    FastAPI --> ChatRouter

    ChatRouter --> TierClassifier
    TierClassifier -->|"DIRECT-tier\n(greetings, meta)"| DirectPath
    TierClassifier -->|"STANDARD/HEAVY-tier"| ReActLoop

    DirectPath --> LLM
    ReActLoop --> IntentClassifier
    ReActLoop --> SkillLoader
    BioSkillsDir --> SkillLoader
    ReActLoop --> Tools
    Tools --> LocalTools
    Tools --> DynamicTools
    Tools --> BioContainerJobs
    BioContainerJobs --> Modal
    LLM --> ReActLoop

    RCSB -.->|"HTTPS"| LocalTools
    NCBI -.->|"HTTPS"| LocalTools
    GDC -.->|"HTTPS"| LocalTools
    ArXiv -.->|"HTTPS"| LocalTools

    Storage --> SessionStore
    Storage --> MessageStore
    Storage --> WorkspaceFS

    ReActLoop --> Storage
    ChatRouter --> Storage
```

---

## 2. LangGraph ReAct Agent Loop (Zoomed)

```mermaid
flowchart LR
    subgraph AgentGraph["LangGraph StateGraph — agent_graph"]
        direction TB
        START([User Query]) --> ClassifyIntent
        
        ClassifyIntent["classify_intent_node()\n───────────────\n• intent_classifier.classify_query()\n• SkillLoader.load_skills()\n• Build SystemMessage with\n  skill_context injection\n• Return {messages, loaded_skills}"]

        ClassifyIntent --> CallModel
        
        CallModel["call_model()\n───────────────\n• Check placeholder key → _mock_llm_response\n• llm.bind_tools(TOOL_DEFINITIONS)\n• llm.invoke(messages)\n• Retry without tools on 400 error\n• Return {messages: [AIMessage]}"]

        CallModel --> ShouldContinue{"tool_calls\npresent?"}

        ShouldContinue -->|Yes| ExecuteTools
        ShouldContinue -->|No| Finalize

        ExecuteTools["tools_node()\n───────────────\n• Extract AIMessage.tool_calls\n• For each: execute_tool(name, args)\n• Returns ToolMessage[]\n• Records to tool_calls log"]
        
        ExecuteTools --> CallModel

        Finalize["finalize_node()\n───────────────\n• Extract last AIMessage.content\n• Return {result: str}"]
        
        Finalize --> END([Response to User])
    end

    style AgentGraph fill:#1a1a2e,stroke:#00d4ff,color:#e0e0e0
    style ClassifyIntent fill:#16213e,stroke:#e94560
    style CallModel fill:#16213e,stroke:#e94560
    style ExecuteTools fill:#16213e,stroke:#e94560
    style Finalize fill:#16213e,stroke:#e94560
```

---

## 3. Tiered Query Routing

```mermaid
flowchart TD
    Q([User Query]) --> T1{regex _DIRECT_PATTERNS\n(greeting, meta, simple def)?}
    T1 -->|Match| DIRECT["QueryTier.DIRECT\n────────────\nRun: direct_llm_response()\nModel: OPENROUTER_DIRECT_MODEL\nTemp: 0.3 | Max: 1024\nNo tools, no skill context\nFast path (< 200ms)"]
    DIRECT --> OUT([Response])

    T1 -->|No match| T2{Short def\n< 12 words\n+ no skills matched?}
    T2 -->|Yes| DIRECT

    T2 -->|No| T3{regex _HEAVY_PATTERNS\n(pipeline, compare, integrate,\nmulti-step, analyze+plot)?}
    T3 -->|Yes| HEAVY["QueryTier.HEAVY\n────────────\nRun: full ReAct loop\nSkill context: max 6000 chars\nMay iterate 3+ rounds\nModal dispatch for bio pipelines"]
    HEAVY --> OUT

    T3 -->|No| T4{skill_paths >= 3?}
    T4 -->|Yes| HEAVY
    T4 -->|No| STANDARD["QueryTier.STANDARD\n────────────\nRun: full ReAct loop\nSkill context: matched domains\n1-3 tool call iterations\nStandard LLM config"]
    STANDARD --> OUT

    style DIRECT fill:#0f3460,stroke:#00d4ff,color:#fff
    style HEAVY fill:#e94560,stroke:#fff,color:#fff
    style STANDARD fill:#1a1a2e,stroke:#e94560,color:#fff
```

---

## 4. Tool Architecture

```mermaid
flowchart TB
    subgraph ToolDef["TOOL_DEFINITIONS — JSON Schema (agent.py)"]
        TD1["download_pdb"]
        TD2["search_literature"]
        TD3["run_bio_pipeline"]
        TD4["run_python_plot"]
        TD5["plotly_plot"]
        TD6["run_modal_job"]
        TD7["create_tool"]
        TD8["create_modal_tool"]
        TD9["execute_python"]
    end

    subgraph ToolImpl["TOOL_IMPLS — Python implementations (tools.py)"]
        TI1["@register_tool('download_pdb')"]
        TI2["@register_tool('search_literature')"]
        TI3["@register_tool('run_bio_pipeline')"]
        TI4["@register_tool('run_python_plot')"]
        TI5["@register_tool('plotly_plot')"]
        TI6["@register_tool('run_modal_job')"]
        TI7["@register_tool('create_tool') → dynamic_tools"]
        TI8["@register_tool('create_modal_tool') → modal_tasks"]
        TI9["@register_tool('execute_python')"]
    end

    subgraph ExecutionSandbox["Sandbox (execute_python, run_python_plot)"]
        SAFEOS["_safe_os\n(os.environ with ***REDACTED***)"]
        Matplotlib["matplotlib (Agg backend)\nseaborn, numpy, pandas"]
        Plotly["plotly (to_html, cdn)"]
    end

    subgraph ModalCloud["Modal.com Cloud"]
        ModalEngine["Modal Engine\n(quay.io/biocontainers)"]
        BioConts["BioContainers\nstar:2.7.11b\nsra-tools:3.4.1\nbioconductor-deseq2"]
    end

    ToolDef --> ToolImpl
    ToolImpl --> ExecutionSandbox
    ToolImpl --> ModalCloud

    TD4 --> TI4
    TD5 --> TI5
    TD6 --> TI6
    TD7 --> TI7
    TD8 --> TI8

    style ToolDef fill:#0f3460,stroke:#00d4ff,color:#e0e0e0
    style ToolImpl fill:#16213e,stroke:#e94560,color:#e0e0e0
    style ExecutionSandbox fill:#1a1a2e,stroke:#7b2ff7,color:#e0e0e0
    style ModalCloud fill:#2d1b4e,stroke:#9d4edd,color:#e0e0e0
```

---

## 5. Frontend — React + SSE Streaming

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant FE as React Frontend
    participant BE as FastAPI /chat/stream
    participant AG as LangGraph Agent
    participant LLM as OpenRouter
    participant ST as SQLite Storage

    U->>FE: POST /api/chat/stream\n(query, session_id, JWT)
    FE->>BE: SSE request
    BE->>AG: run_stream(query, session_id)
    AG->>ST: add_message(user, query)
    ST-->>AG: msg_id
    AG->>AG: classify_tier() → STANDARD
    AG->>AG: agent_graph.stream()
    AG->>LLM: invoke(messages + skill_context)
    LLM-->>AG: AIMessage(tool_calls: [download_pdb])
    AG->>AG: tools_node() → execute_tool
    AG->>BE: {"event": "tool_call", "data": {...}}
    AG->>BE: {"event": "tool_result", "data": {...}}
    AG->>BE: {"event": "chunk", "data": {"content": "..."}}
    AG->>ST: update_assistant_message(content, tool_calls)
    AG->>BE: {"event": "done", "data": {"response": "...", "skills": [...], "tool_calls": [...]}}
    BE-->>FE: SSE stream
    FE-->>U: Real-time token-by-token render

    Note over U,LLM: visualization events also emitted:\n{"event": "visualization", "data": {"type": "plotly", "html": "..."}}
    Note over U,LLM: {"event": "visualization", "data": {"type": "structure", "pdb_id": "1ABC"}}
```

---

## 6. bioSkills — 26 Domain Skill Contexts

```mermaid
flowchart TB
    subgraph SkillTree["bioSkills/ Directory — 26 Skill Domains"]
        direction TB
        SB["structural-biology/\nstructure-io | geometric-analysis | alphafold-predictions"]
        SEQ["sequence/\nsequence-io | sequence-manipulation | alignment"]
        VAR["variant-calling/\nvcf-basics | variant-annotation | clinical-interpretation"]
        EXP["expression & transcriptomics/\nrna-quantification | differential-expression"]
        GEN["genome/\nread-alignment | read-qc | methylation-analysis"]
        FUN["functional genomics/\nchip-seq | atac-seq"]
        COMP["comparative & population/\nphylogenetics | population-genetics"]
        MICRO["microbiome/\nmetagenomics | microbiome"]
        PROT["proteomics"]
        PATH["pathway-analysis | database-access\n(database-access/interaction-databases)"]
        SC["single-cell"]
        CRISPR["crispr-screens"]
        ML["machine-learning"]
        CLIN["clinical-biostatistics"]
        DATAVIZ["data-visualization"]
        PRIMER["primer-design"]
        CHEMO["chemoinformatics"]
    end

    subgraph SkillLoad["Skill Loading Pipeline"]
        IC["classify_intent_node()\n→ intent_classifier.classify_query()"]
        SL["SkillLoader.load_skills(skill_paths)\n→ read SKILL.md from disk (cached)"]
        SCB["SkillContextBuilder.build_context()\n→ max 6000 chars, truncate if needed"]
        INJ["Inject as {skill_context} into\nstandard system prompt"]
    end

    IC --> SL
    SL --> SCB
    SCB --> INJ

    SkillTree --> SL

    style SkillTree fill:#0f3460,stroke:#00d4ff,color:#e0e0e0
    style SkillLoad fill:#16213e,stroke:#e94560,color:#e0e0e0
```

---

## 7. Session Persistence & State

```mermaid
flowchart TB
    subgraph DB["SQLite — WAL Mode (storage.py)"]
        SESSIONS["sessions table\n───────────────\nid, user_id, title, created_at,\nupdated_at, metadata JSON"]
        MESSAGES["messages table\n───────────────\nid, session_id, role, content,\nskills JSON, tool_calls JSON,\nthoughts JSON, visualization JSON,\ncreated_at, updated_at"]
    end

    subgraph Workspace["Workspace FS"]
        WD["{user_id}/{session_id}/\n────────────────\nbackground_jobs/\nuser_uploads/\nreports/"]
    end

    subgraph Checkpoint["LangGraph Checkpointer"]
        CG["SqliteSaver (WAL conn)\n───────────────\nPersists agent state per thread_id\nEnables conversation resumption"]
    end

    CG --> SESSIONS
    CG --> MESSAGES
    WD --> Workspace

    style DB fill:#0f3460,stroke:#00d4ff,color:#e0e0e0
    style Workspace fill:#1a1a2e,stroke:#7b2ff7,color:#e0e0e0
    style Checkpoint fill:#16213e,stroke:#e94560,color:#e0e0e0
```

---

## 8. Authentication & Security

```mermaid
flowchart TB
    subgraph Auth["JWT Auth (auth.py)"]
        Register["POST /api/auth/register\n───────────\nemail, password → bcrypt → DB\nReturns JWT (HS256)"]
        Login["POST /api/auth/login\n───────────\nemail, password → verify → JWT\nToken: esapiens_token (localStorage)"]
        Me["GET /api/auth/me\n───────────\nBearer {JWT} → user profile"]
    end

    subgraph Security["Secret Hygiene (tools.py)"]
        SH["_SECRET_ENV_VARS\n───────────\nOPENROUTER_API_KEY → ***REDACTED***\nMODAL_TOKEN_ID → ***REDACTED***\nJWT_SECRET → ***REDACTED***\nUsed in execute_python sandbox\nand tool result masking"]
    end

    subgraph CORS["CORS Policy (app.py)"]
        CP["CORS_ORIGINS env var\n───────────\ndefault: localhost:5173,4173,3000\nRestrict to known frontend origins\ncredentials=False, GET/POST/DELETE"]
    end

    Register --> Auth
    Login --> Auth
    Auth --> CP
    SH --> Security

    style Auth fill:#0f3460,stroke:#00d4ff,color:#e0e0e0
    style Security fill:#16213e,stroke:#e94560,color:#e0e0e0
    style CORS fill:#1a1a2e,stroke:#7b2ff7,color:#e0e0e0
```

---

## Legend

| Color | Layer |
|-------|-------|
| `#0f3460` | VPS / Backend services |
| `#16213e` | Core agent logic (LangGraph nodes) |
| `#e94560` | Tool system / Dynamic components |
| `#7b2ff7` | Workspace / Persistence layer |
| `#2d1b4e` | Cloud / External services |
| `#1a1a2e` | UI / Client layer |