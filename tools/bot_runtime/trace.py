"""Append-only source-free observations, never execution or approval authority."""
import os
import re
import traceback
from contextlib import contextmanager
from functools import wraps
from time import perf_counter_ns
from uuid import uuid4

from tools.quality_dashboard.artifacts import ArtifactError, digest, sha

from .store import directory, now, read, write

VERSION='bot-request-trace-1.0'
CODE=re.compile(r'(?:m7_|m8_|embedding_|BOT_|INVALID_|SOURCE_|TRUST_|PRESERVATION_)[A-Za-z0-9_: .-]{1,220}\Z')
SECRET=re.compile(r'(?:bearer\s+|sk-[A-Za-z0-9]|api[_-]?key|password|authorization\s*[=:])',re.IGNORECASE)


def failure(error,root):
    """No arguments, locals, source lines, environment or arbitrary error bodies.

    Preserve exact recognized internal codes. Untrusted/provider text is hashed,
    not logged: even a private trace must not become a credential/body dump.
    """
    try:text=str(error)
    except Exception:text='EXCEPTION_TEXT_UNAVAILABLE'  # noqa: BLE001 - diagnostic conversion only
    code=text if CODE.fullmatch(text) and not SECRET.search(text) else None
    frames=[]
    for item in traceback.extract_tb(error.__traceback__):
        from pathlib import Path
        path=Path(item.filename)
        name=path.relative_to(root).as_posix() if path.is_relative_to(root) else path.name
        frames.append({'file':name,'function':item.name,'line':item.lineno})
    return {'exception_type':type(error).__name__,'error_code':code,
        'message_status':'RECOGNIZED_INTERNAL_CODE' if code else 'UNTRUSTED_TEXT_OMITTED',
        'message_sha256':digest(text),'frames':frames}


class RequestTrace:
    def __init__(self,root,folder,*,question_id,run_id,mode,question_reference):
        from pathlib import Path
        self.root=Path(root);self.folder=Path(folder)/'REQUEST_TRACE'
        self.identity={'schema':VERSION,'question_id':question_id,'run_id':run_id,
                       'mode':mode,'question_reference':question_reference}
        self.seq=0;self.previous=None;self.degraded=False;self.seen=set()
        try:
            directory(self.root,self.folder.relative_to(self.root).as_posix())
            self.spool=directory(self.root,'workspace/bot-trace-spool')
        except (OSError,ValueError,TypeError):
            self.degraded=True
        self.emit('QUESTION_RECEIVED','COMPLETED',operation='Registered question reference')

    def _write(self,path,value):
        # Failed/partial writes remain private spool diagnostics, outside the
        # execution seal. An optional logging failure cannot corrupt a result.
        temporary=self.spool/(uuid4().hex+'.json')
        write(temporary,value)
        os.link(temporary,path)  # Atomic publication, exclusive target; no overwrite.
        descriptor=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        temporary.unlink()

    def emit(self,stage,status,*,operation=None,duration_ms=None,detail=None):
        if self.degraded:return
        value=self.identity|{'sequence':self.seq,'previous_sha256':self.previous,
            'timestamp':now(),'stage':stage,'status':status,'operation':operation or stage,
            'duration_ms':duration_ms,'detail':detail}
        try:
            file=self.folder/f'{self.seq:06d}.json';self._write(file,value)
            self.previous=sha(file);self.seq+=1
        except (OSError,ValueError,TypeError):
            self.degraded=True

    def error(self,stage,error,*,operation=None,duration_ms=None):
        detail=failure(error,self.root) if id(error) not in self.seen else {'nested_failure':True}
        self.seen.add(id(error))
        self.emit(stage,'FAILED',operation=operation,duration_ms=duration_ms,detail=detail)

    @contextmanager
    def span(self,stage,*,operation=None):
        start=perf_counter_ns();self.emit(stage,'RUNNING',operation=operation)
        try:
            yield
        except Exception as error:
            self.error(stage,error,operation=operation,duration_ms=(perf_counter_ns()-start)/1e6)
            raise
        else:
            self.emit(stage,'COMPLETED',operation=operation,duration_ms=(perf_counter_ns()-start)/1e6)

    def attach(self,timer):
        original=timer.span
        @contextmanager
        def observed(stage):
            with self.span(stage),original(stage):yield
        timer.span=observed

    @contextmanager
    def observe(self,owner,method,stage):
        original=getattr(owner,method);own=method in vars(owner)
        previous=vars(owner).get(method)
        @wraps(original)
        def observed(*args,**kwargs):
            with self.span(stage):return original(*args,**kwargs)
        setattr(owner,method,observed)
        try:yield
        finally:
            if own:setattr(owner,method,previous)
            else:delattr(owner,method)

    def finish(self,status,*,request_sha256=None,package_sha256=None):
        self.emit('EXECUTION_RESULT',status,detail={'request_sha256':request_sha256,
                    'package_sha256':package_sha256})
        if self.degraded:return {'status':'TRACE_CAPTURE_FAILED','artifact':None}
        try:
            self._write(self.folder/'SEAL.json',self.identity|{
                'files':{p.name:sha(p) for p in self.folder.glob('[0-9]*.json')}})
            return {'status':'SEALED','artifact':(self.folder/'SEAL.json').relative_to(self.root).as_posix()}
        except (OSError,ValueError,TypeError):
            self.degraded=True
            return {'status':'TRACE_CAPTURE_FAILED','artifact':None}


def events(folder,*,question_id,run_id,question_reference,sealed=True):
    """Progress is observational only until the containing execution seal verifies."""
    if sealed:
        m=read(folder/'SEAL.json')
        if m.get('schema')!=VERSION:raise ArtifactError('TRACE_SCHEMA_INVALID')
        if (m['question_id'],m['run_id'],m['question_reference'])!=(question_id,run_id,question_reference):
            raise ArtifactError('TRACE_IDENTITY_MISMATCH')
        if set(m['files'])!={p.name for p in folder.glob('[0-9]*.json')}:
            raise ArtifactError('TRACE_EVENT_INVENTORY_CHANGED')
        for name,expected in m['files'].items():
            if not re.fullmatch(r'[0-9]{6}\.json',name) or sha(folder/name)!=expected:
                raise ArtifactError('TRACE_EVENT_HASH_CHANGED')
    result=[];previous=None
    for index,file in enumerate(sorted(folder.glob('[0-9]*.json'))):
        row=read(file)
        if (file.name!=f'{index:06d}.json' or row.get('schema')!=VERSION
                or row.get('sequence')!=index or row.get('previous_sha256')!=previous
                or row.get('question_id')!=question_id or row.get('run_id')!=run_id
                or row.get('question_reference')!=question_reference):
            raise ArtifactError('TRACE_CHAIN_OR_BINDING_CHANGED')
        previous=sha(file);result.append(row)
    if not result:raise ArtifactError('TRACE_UNAVAILABLE')
    return result
