from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import cvxpy as cp


@dataclass
class CvxpyEntityInfo:
    name: str
    shape: Tuple[int, ...]
    size: int
    is_boolean: bool = False
    is_integer: bool = False
    has_value: Optional[bool] = None  # for Parameters


@dataclass
class CvxpyProblemSummary:
    status: Optional[str]
    objective_sense: str
    is_dcp: bool
    is_dqcp: bool
    is_dpp: bool
    has_parameters: bool

    n_constraints: int
    n_variables: int
    n_scalar_variables: int
    n_boolean_vars: int
    n_scalar_boolean: int
    n_integer_vars: int
    n_scalar_integer: int
    
    # Constraint breakdown (if available)
    n_scalar_eq_constr: Optional[int] = None
    n_scalar_leq_constr: Optional[int] = None
    
    # If solved
    solver_name: Optional[str] = None
    solve_time: Optional[float] = None
    optimal_value: Optional[float] = None

    # Optional detailed listings
    variables_detail: Optional[List[CvxpyEntityInfo]] = None
    parameters_detail: Optional[List[CvxpyEntityInfo]] = None
    

# def _var_is_boolean(v: cp.Variable) -> bool:
#     return bool(getattr(v, "boolean", False))


# def _var_is_integer(v: cp.Variable) -> bool:
#     # In CVXPY, boolean variables are also integer.
#     return bool(getattr(v, "integer", False))

def _var_is_boolean(v):
    attrs = getattr(v, "attributes", {})
    return bool(attrs.get("boolean", False))

def _var_is_integer(v):
    attrs = getattr(v, "attributes", {})
    # boolean variables are also integer in CVXPY's attribute system
    return bool(attrs.get("integer", False) or attrs.get("boolean", False))

def _get_name(obj) -> str:
    # CVXPY variables/params generally have .name()
    try:
        return obj.name()
    except Exception:
        return str(obj)


def _collect_variable_info(prob: cp.Problem) -> List[CvxpyEntityInfo]:
    info = []
    for v in prob.variables():
        info.append(
            CvxpyEntityInfo(
                name=_get_name(v),
                shape=tuple(v.shape),
                size=int(v.size),
                is_boolean=_var_is_boolean(v),
                is_integer=_var_is_integer(v),
            )
        )
    return info

def _collect_parameter_info(prob: cp.Problem) -> List[CvxpyEntityInfo]:
    info = []
    for p in prob.parameters():
        has_value = p.value is not None
        info.append(
            CvxpyEntityInfo(
                name=_get_name(p),
                shape=tuple(p.shape),
                size=int(p.size),
                has_value=has_value,
            )
        )
    return info

def summarize_cvxpy_problem(
    prob: cp.Problem,
    include_entity_details: bool = False,   # <--- CHANGE HERE to include variable/parameter listing
    sort_entities_by: str = "name",         # <--- CHANGE HERE ("name" or "size")
    as_dict: bool = False,
) -> Dict[str, Any] | CvxpyProblemSummary:
    """
    Summarize a CVXPY Problem.

    Parameters
    ----------
    include_entity_details : bool
        If True, include per-variable/per-parameter name/shape/size flags.
    sort_entities_by : str
        "name" or "size" sorting for the detailed listings.
    as_dict : bool
        Return a plain dict instead of dataclasses.

    Returns
    -------
    CvxpyProblemSummary or dict
    """
    
    vars_ = list(prob.variables())
    cons_ = list(prob.constraints)
    params_ = list(prob.parameters())

    n_vars = len(vars_)
    n_scalar = int(sum(v.size for v in vars_))

    bool_vars = [v for v in vars_ if _var_is_boolean(v)]
    int_vars = [v for v in vars_ if _var_is_integer(v)]

    n_bool = len(bool_vars)
    n_scalar_bool = int(sum(v.size for v in bool_vars))

    n_int = len(int_vars)
    n_scalar_int = int(sum(v.size for v in int_vars))

    objective_sense = "minimize" if isinstance(prob.objective, cp.Minimize) else "maximize"

    # DCP / DQCP / DPP checks (guarded)
    try:
        is_dcp = bool(prob.is_dcp())
    except Exception:
        is_dcp = False
    try:
        is_dqcp = bool(prob.is_dqcp())
    except Exception:
        is_dqcp = False
    try:
        is_dpp = bool(prob.is_dpp())
    except Exception:
        is_dpp = False

    has_params = len(params_) > 0
    
    # size_metrics (built-in) gives scalar constraint breakdown when available
    n_scalar_eq_constr = None
    n_scalar_leq_constr = None
    try:
        sm = prob.size_metrics
        n_scalar_eq_constr = int(getattr(sm, "num_scalar_eq_constr", None)) if hasattr(sm, "num_scalar_eq_constr") else None
        n_scalar_leq_constr = int(getattr(sm, "num_scalar_leq_constr", None)) if hasattr(sm, "num_scalar_leq_constr") else None
    except Exception:
        pass
    
    # Solver stats
    solver_name = None
    solve_time = None
    if prob.solver_stats is not None:
        solver_name = getattr(prob.solver_stats, "solver_name", None)
        solve_time = getattr(prob.solver_stats, "solve_time", None)

    optimal_value = None
    if prob.value is not None:
        try:
            optimal_value = float(prob.value)
        except Exception:
            optimal_value = None
            
    variables_detail = None
    parameters_detail = None
    if include_entity_details:
        variables_detail = _collect_variable_info(prob)
        parameters_detail = _collect_parameter_info(prob)

        # Sorting: CHANGE HERE if you want a different ordering
        if sort_entities_by == "size":
            variables_detail.sort(key=lambda x: x.size, reverse=True)
            parameters_detail.sort(key=lambda x: x.size, reverse=True)
        else:  # default "name"
            variables_detail.sort(key=lambda x: x.name)
            parameters_detail.sort(key=lambda x: x.name)
    
    summary = CvxpyProblemSummary(
        status=getattr(prob, "status", None),
        objective_sense=objective_sense,
        is_dcp=is_dcp,
        is_dqcp=is_dqcp,
        is_dpp=is_dpp,
        has_parameters=has_params,

        n_constraints=len(cons_),
        n_variables=n_vars,
        n_scalar_variables=n_scalar,
        n_boolean_vars=n_bool,
        n_scalar_boolean=n_scalar_bool,
        n_integer_vars=n_int,
        n_scalar_integer=n_scalar_int,

        n_scalar_eq_constr=n_scalar_eq_constr,
        n_scalar_leq_constr=n_scalar_leq_constr,

        solver_name=solver_name,
        solve_time=solve_time,
        optimal_value=optimal_value,

        variables_detail=variables_detail,
        parameters_detail=parameters_detail,
    )
    
    
    return asdict(summary) if as_dict else summary

def print_summary(
    prob: cp.Problem,
    include_entity_details: bool = False,  # <--- CHANGE HERE to turn listings on/off
    sort_entities_by: str = "name",
    max_entities: Optional[int] = None,    # <--- CHANGE HERE to cap output length
) -> None:
    """
    Pretty-print summary for quick debugging.
    """
    s = summarize_cvxpy_problem(
        prob,
        include_entity_details=include_entity_details,
        sort_entities_by=sort_entities_by,
        as_dict=True,
    )
    
    print("CVXPY Problem Summary")
    print(f"  status: {s['status']}")
    print(f"  objective: {s['objective_sense']}")
    print(f"  DCP/DQCP/DPP: {s['is_dcp']}/{s['is_dqcp']}/{s['is_dpp']}")
    print(f"  has_parameters: {s['has_parameters']}")
    print("")

    print(f"  constraints (objects): {s['n_constraints']}")
    if s.get("n_scalar_eq_constr") is not None or s.get("n_scalar_leq_constr") is not None:
        print(f"  constraints (scalar eq/leq): {s.get('n_scalar_eq_constr')}/{s.get('n_scalar_leq_constr')}")
    print("")
    
    print(f"  variables (objects): {s['n_variables']}")
    print(f"  variables (scalar):  {s['n_scalar_variables']}")
    print(f"  boolean vars (objects/scalar): {s['n_boolean_vars']}/{s['n_scalar_boolean']}")
    print(f"  integer vars (objects/scalar): {s['n_integer_vars']}/{s['n_scalar_integer']}")
    print("")

    print(f"  solver: {s['solver_name']}, solve_time: {s['solve_time']}, value: {s['optimal_value']}")

    if include_entity_details:
        print("\nVariables:")
        vars_detail = s["variables_detail"] or []
        if max_entities is not None:
            vars_detail = vars_detail[:max_entities]
        for v in vars_detail:
            flags = []
            if v["is_boolean"]:
                flags.append("bool")
            if v["is_integer"]:
                flags.append("int")
            flag_str = f" [{' '.join(flags)}]" if flags else ""
            print(f"  - {v['name']}: shape={tuple(v['shape'])}, size={v['size']}{flag_str}")

        print("\nParameters:")
        params_detail = s["parameters_detail"] or []
        if max_entities is not None:
            params_detail = params_detail[:max_entities]
        for p in params_detail:
            hv = "set" if p["has_value"] else "unset"
            print(f"  - {p['name']}: shape={tuple(p['shape'])}, size={p['size']} [{hv}]")

